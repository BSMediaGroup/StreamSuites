import asyncio
import json
from typing import AsyncIterator, Dict, Any, List, Optional

import httpx

from shared.logging.logger import get_logger

log = get_logger("rumble.chat.tombi_stream")


class StreamDisconnected(Exception):
    """Raised when the chat stream closes, idles out, or returns an error."""


class TombiStreamClient:
    """
    Lightweight streaming client for the Tombi chat endpoint.

    This client relies solely on the confirmed endpoint:
        https://web7.rumble.com/chat/api/chat/{chat_id}/stream

    It uses the authenticated browser session cookies and mirrors the
    browser headers to prevent API bans.
    """

    STREAM_URL = "https://web7.rumble.com/chat/api/chat/{chat_id}/stream"

    def __init__(
        self,
        chat_id: str,
        *,
        cookies: Optional[httpx._models.CookieTypes] = None,
        cookie_header: Optional[str] = None,
        watch_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        idle_timeout: float = 30.0,
    ):
        self.chat_id = str(chat_id)
        self._cookie_header = cookie_header
        self._idle_timeout = idle_timeout

        base_headers = {
            "User-Agent": headers.get("User-Agent") if headers else None,
            "Origin": "https://rumble.com",
            "Referer": watch_url or "https://rumble.com/",
            "Accept": "application/json",
        }
        if headers:
            base_headers.update(headers)

        self._base_headers = {k: v for k, v in base_headers.items() if v}

        self._client = httpx.AsyncClient(
            headers=self._base_headers,
            cookies=cookies,
            timeout=httpx.Timeout(10.0, read=None),
            follow_redirects=True,
        )

    # ------------------------------------------------------------

    async def iter_messages(self) -> AsyncIterator[Dict[str, Any]]:
        url = self.STREAM_URL.format(chat_id=self.chat_id)
        headers = dict(self._base_headers)
        if self._cookie_header:
            headers["Cookie"] = self._cookie_header

        log.info("Connecting to Tombi chat stream (chat_id=%s)", self.chat_id)
        async with self._client.stream("GET", url, headers=headers) as resp:
            status = resp.status_code
            if status != 200:
                body_preview = ""
                try:
                    raw = await resp.aread()
                    body_preview = raw.decode(errors="ignore")[:500]
                except Exception:
                    body_preview = "<unreadable>"
                raise StreamDisconnected(
                    f"Chat stream HTTP {status} (chat_id={self.chat_id}) body={body_preview}"
                )

            line_iter = resp.aiter_lines()
            while True:
                try:
                    line = await asyncio.wait_for(line_iter.__anext__(), timeout=self._idle_timeout)
                except asyncio.TimeoutError as e:
                    raise StreamDisconnected(
                        f"Chat stream idle for {self._idle_timeout:.1f}s (chat_id={self.chat_id})"
                    ) from e
                except StopAsyncIteration:
                    raise StreamDisconnected(f"Chat stream closed (chat_id={self.chat_id})")

                if line is None:
                    continue

                stripped = line.strip()
                if not stripped:
                    continue

                messages = self._parse_line(stripped)
                for msg in messages:
                    yield msg

    # ------------------------------------------------------------

    def _parse_line(self, line: str) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(line)
        except Exception:
            log.debug("Ignoring non-JSON chat line")
            return []

        if not isinstance(payload, dict):
            return []

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        messages = data.get("messages") if isinstance(data, dict) else None

        out: List[Dict[str, Any]] = []

        if isinstance(messages, list):
            out.extend([m for m in messages if isinstance(m, dict)])

        if not out and isinstance(payload, dict):
            if isinstance(payload.get("text"), str) and (
                isinstance(payload.get("user_name"), str) or isinstance(payload.get("username"), str)
            ):
                out.append(payload)

        return out

    # ------------------------------------------------------------

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass
