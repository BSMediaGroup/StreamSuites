"""HTTP API server for unified chat + livechat surfaces."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from shared.chat.events import create_chat_event
from shared.logging.logger import get_logger
from shared.runtime import chat_context
from shared.storage.chat_events import (
    get_stream,
    list_streams,
    paginate_events,
    range_events,
    tail_events,
)
from shared.storage.chat_events.writer import write_event

log = get_logger("services.chat_api")


@dataclass
class SyntheticChatConfig:
    enabled: bool = True
    creator_token: str = "dev-creator-token"
    discord_bot_token: str = "dev-discord-token"
    rate_limit_per_minute: int = 30


@dataclass
class ChatApiConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8210
    allow_origins: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class ChatRuntimeConfig:
    api: ChatApiConfig = field(default_factory=ChatApiConfig)
    synthetic: SyntheticChatConfig = field(default_factory=SyntheticChatConfig)


class RateLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, int(max_per_minute))
        self._lock = threading.Lock()
        self._buckets: Dict[str, List[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            bucket = self._buckets.setdefault(key, [])
            bucket[:] = [ts for ts in bucket if ts >= window_start]
            if len(bucket) >= self._max:
                return False
            bucket.append(now)
            return True


class ChatApiServer:
    def __init__(self, config: ChatRuntimeConfig, base_dir: Path | str = ".") -> None:
        self._config = config
        self._base_dir = Path(base_dir)
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[ThreadingHTTPServer] = None
        self._rate_limiter = RateLimiter(config.synthetic.rate_limit_per_minute)

    def start(self) -> None:
        if not self._config.api.enabled:
            log.info("Chat API server disabled via config")
            return
        if self._thread and self._thread.is_alive():
            return

        handler = self._build_handler()
        self._server = ThreadingHTTPServer(
            (self._config.api.host, int(self._config.api.port)),
            handler,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log.info(
            "Chat API server running on %s:%s",
            self._config.api.host,
            self._config.api.port,
        )

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        log.info("Chat API server stopped")

    def _build_handler(self):
        config = self._config
        base_dir = self._base_dir
        rate_limiter = self._rate_limiter

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(base_dir), **kwargs)

            def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._apply_cors()
                self.end_headers()
                self.wfile.write(body)

            def _apply_cors(self) -> None:
                origins = config.api.allow_origins
                if not origins:
                    return
                origin = self.headers.get("Origin")
                if "*" in origins:
                    self.send_header("Access-Control-Allow-Origin", "*")
                elif origin and origin in origins:
                    self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Authorization, Content-Type, X-StreamSuites-Token",
                )
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

            def do_OPTIONS(self) -> None:
                self.send_response(HTTPStatus.NO_CONTENT)
                self._apply_cors()
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802 - stdlib signature
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/"):
                    return self._handle_api_get(parsed)

                if parsed.path.rstrip("/") == "/livechat":
                    self.path = "/livechat/index.html"
                return super().do_GET()

            def do_POST(self) -> None:  # noqa: N802 - stdlib signature
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/"):
                    return self._handle_api_post(parsed)
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

            def _read_json_body(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return {}
                return payload if isinstance(payload, dict) else {}

            def _resolve_stream_id(self, query: Dict[str, List[str]]) -> Optional[str]:
                stream_id = (query.get("stream_id") or [None])[0]
                if stream_id:
                    return stream_id
                context = chat_context.get_context()
                return context.stream_id

            def _handle_api_get(self, parsed):
                query = parse_qs(parsed.query)
                path = parsed.path

                if path == "/api/streams":
                    streams = list_streams()
                    context = chat_context.get_context()
                    return self._send_json(
                        HTTPStatus.OK,
                        {
                            "streams": streams,
                            "active_context": context.to_dict(),
                        },
                    )

                if path == "/api/chat/tail":
                    limit = int((query.get("limit") or ["50"])[0])
                    stream_id = self._resolve_stream_id(query)
                    events = tail_events(stream_id or "", limit=limit) if stream_id else []
                    context = chat_context.get_context()
                    return self._send_json(
                        HTTPStatus.OK,
                        {
                            "events": events,
                            "context": context.to_dict(),
                        },
                    )

                if path == "/api/chat/events":
                    limit = int((query.get("limit") or ["50"])[0])
                    cursor = (query.get("cursor") or [None])[0]
                    from_ts = (query.get("from_ts") or [None])[0]
                    to_ts = (query.get("to_ts") or [None])[0]
                    stream_id = self._resolve_stream_id(query)

                    events: List[Dict[str, Any]] = []
                    next_cursor: Optional[str] = None

                    if stream_id:
                        if from_ts or to_ts:
                            events = range_events(stream_id, from_ts, to_ts)
                        else:
                            events, next_cursor = paginate_events(
                                stream_id, limit=limit, cursor=cursor
                            )

                    context = chat_context.get_context()
                    return self._send_json(
                        HTTPStatus.OK,
                        {
                            "events": events,
                            "next_cursor": next_cursor,
                            "context": context.to_dict(),
                        },
                    )

                self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

            def _authorize_synthetic(self, author_source: str) -> bool:
                token = self.headers.get("Authorization") or self.headers.get("X-StreamSuites-Token")
                if token and token.lower().startswith("bearer "):
                    token = token[7:]

                expected = None
                if author_source == "creator":
                    expected = config.synthetic.creator_token
                elif author_source == "discord":
                    expected = config.synthetic.discord_bot_token

                if not expected:
                    return False
                return token == expected

            def _handle_api_post(self, parsed):
                path = parsed.path
                payload = self._read_json_body()

                if path == "/api/replay/select":
                    stream_id = payload.get("stream_id")
                    if not stream_id:
                        return self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"error": "stream_id is required"},
                        )
                    if not get_stream(stream_id):
                        return self._send_json(
                            HTTPStatus.NOT_FOUND,
                            {"error": "stream_id not found"},
                        )
                    context = chat_context.select_replay(stream_id)
                    return self._send_json(
                        HTTPStatus.OK,
                        {"context": context.to_dict()},
                    )

                if path == "/api/replay/clear":
                    context = chat_context.clear_replay()
                    return self._send_json(
                        HTTPStatus.OK,
                        {"context": context.to_dict()},
                    )

                if path == "/api/chat/synthetic":
                    if not config.synthetic.enabled:
                        return self._send_json(
                            HTTPStatus.FORBIDDEN,
                            {"error": "synthetic chat disabled"},
                        )

                    author_source = (payload.get("author_source") or "").lower().strip()
                    if author_source not in {"creator", "discord"}:
                        return self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"error": "author_source must be creator or discord"},
                        )

                    if not self._authorize_synthetic(author_source):
                        return self._send_json(
                            HTTPStatus.UNAUTHORIZED,
                            {"error": "unauthorized"},
                        )

                    token_key = f"{author_source}:{self.headers.get('Authorization') or self.headers.get('X-StreamSuites-Token') or ''}"
                    if not rate_limiter.allow(token_key):
                        return self._send_json(
                            HTTPStatus.TOO_MANY_REQUESTS,
                            {"error": "rate limit exceeded"},
                        )

                    stream_id = payload.get("stream_id")
                    author_id = payload.get("author_id")
                    display_name = payload.get("display_name")
                    avatar_url = payload.get("avatar_url")
                    text = payload.get("text")

                    if not stream_id or not author_id or not display_name or not text:
                        return self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"error": "stream_id, author_id, display_name, text required"},
                        )

                    source_platform = "streamsuites" if author_source == "creator" else "discord"
                    roles = ["creator"] if author_source == "creator" else ["bot"]

                    event = create_chat_event(
                        stream_id=stream_id,
                        source_platform=source_platform,
                        author_id=str(author_id),
                        display_name=str(display_name),
                        text=str(text),
                        avatar_url=avatar_url,
                        roles=roles,
                        is_synthetic=True,
                        raw={
                            "author_source": author_source,
                        },
                    )

                    write_event(event)
                    context = chat_context.get_context()
                    return self._send_json(
                        HTTPStatus.OK,
                        {"event": event.to_dict(), "context": context.to_dict()},
                    )

                self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

            def log_message(self, format: str, *args: Any) -> None:
                log.info("%s - %s", self.address_string(), format % args)

        return Handler


__all__ = ["ChatApiServer", "ChatRuntimeConfig", "ChatApiConfig", "SyntheticChatConfig"]
