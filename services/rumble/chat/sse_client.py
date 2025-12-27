import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional, List, Dict

import httpx

from shared.logging.logger import get_logger

log = get_logger("rumble.chat.sse")


class SSEUnavailable(Exception):
    """
    Raised when the SSE endpoint explicitly signals that streaming is not
    available (e.g., repeated non-SSE responses). Callers can use this to
    downgrade to alternate ingest paths instead of retrying forever.

    HTTP 204 is now treated as a keepalive, not a failure. The previous logic
    escalated 204s into hard disablement which prevented the worker from
    falling back deterministically. The behavior change is documented here
    because it shortens the old failure path and keeps the retry window flat
    when the server simply withholds data.
    """

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class SSEEvent:
    """
    Lightweight container for SSE frames.

    The Rumble endpoint emits event/data/id triplets using the standard
    Server-Sent Events framing. We keep it explicit to make downstream
    parsing and reconnection handling easier to reason about.
    """

    event: str
    data: str
    event_id: Optional[str] = None


class RumbleChatSSEClient:
    """
    Minimal SSE client for Rumble chat streams.

    Rules:
    - Accepts a chat_id and connects to the authoritative SSE endpoint
    - Handles keepalives, reconnect backoff, and Last-Event-ID for idempotency
    - Yields decoded SSEEvent objects without opinionated parsing
    """

    STREAM_URL = "https://web7.rumble.com/chat/api/chat/{chat_id}/stream"

    def __init__(
        self,
        chat_id: str,
        *,
        client: Optional[httpx.AsyncClient] = None,
        cookies: Optional[httpx._models.CookieTypes] = None,
        cookie_header: Optional[str] = None,
        watch_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.chat_id = str(chat_id)

        base_headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://rumble.com",
            "Referer": watch_url or "https://rumble.com/",
        }

        if headers:
            base_headers.update(headers)

        self._base_headers = base_headers
        self._cookie_header = cookie_header

        # Allow caller to supply a shared client; otherwise own lifecycle
        self._client = client or httpx.AsyncClient(
            headers=self._base_headers,
            cookies=cookies,
            timeout=httpx.Timeout(10.0, read=None),
            follow_redirects=True,
        )

        self._client_owned = client is None
        self._closed = False
        self._last_event_id: Optional[str] = None

    # ------------------------------------------------------------------

    async def iter_events(self) -> AsyncIterator[SSEEvent]:
        """
        Connect to the SSE endpoint and yield parsed frames.

        This loop is intentionally tolerant of network hiccups; it will
        reconnect with bounded backoff and reuse Last-Event-ID when the
        server provides one. Callers should cancel/close to stop iteration.
        """

        url = self.STREAM_URL.format(chat_id=self.chat_id)

        backoff_seconds = 1.0
        failure_count = 0

        while not self._closed:
            headers = dict(self._base_headers)
            if self._last_event_id:
                headers["Last-Event-ID"] = self._last_event_id
            if self._cookie_header:
                headers["Cookie"] = self._cookie_header

            log.debug(
                "SSE headers (chat_id=%s, cookies=%s): %s",
                self.chat_id,
                len(self._client.cookies or []),
                headers,
            )

            try:
                async with self._client.stream("GET", url, headers=headers) as resp:
                    ct = resp.headers.get("content-type")
                    status = resp.status_code

                    if status == 204:
                        log.info(
                            "SSE keepalive HTTP 204 (chat_id=%s) — waiting for events",
                            self.chat_id,
                        )
                        # 204 is an empty keepalive; do not backoff exponentially.
                        failure_count = 0
                        await asyncio.sleep(2)
                        continue

                    if status != 200 or (ct and "text/event-stream" not in ct):
                        body_preview = ""
                        try:
                            raw = await resp.aread()
                            body_preview = raw.decode(errors="ignore")[:500]
                        except Exception:
                            body_preview = "<unreadable>"

                        log.error(
                            "SSE connection failed [%s] content-type=%s url=%s body=%s",
                            status,
                            ct,
                            url,
                            body_preview,
                        )
                        log.debug(
                            "SSE response headers (chat_id=%s): %s",
                            self.chat_id,
                            dict(resp.headers),
                        )

                        failure_count += 1
                        if failure_count >= 3:
                            self._closed = True
                            raise SSEUnavailable(
                                f"Failed to establish SSE after {failure_count} attempts (last status={status})",
                                status_code=status,
                            )

                        log.debug(
                            "SSE retrying in %.1fs (chat_id=%s)",
                            backoff_seconds,
                            self.chat_id,
                        )
                        await asyncio.sleep(backoff_seconds)
                        backoff_seconds = min(backoff_seconds * 2, 30.0)
                        continue

                    log.info("Rumble SSE stream connected (chat_id=%s)", self.chat_id)
                    log.debug(
                        "SSE response headers (chat_id=%s): %s",
                        self.chat_id,
                        dict(resp.headers),
                    )
                    backoff_seconds = 1.0
                    failure_count = 0

                    async for event in self._read_stream(resp):
                        if event.event_id:
                            self._last_event_id = event.event_id
                        yield event

            except asyncio.CancelledError:
                raise

            except SSEUnavailable:
                raise

            except Exception as e:
                failure_count += 1
                log.warning(
                    "SSE stream error (chat_id=%s, attempt=%s): %s",
                    self.chat_id,
                    failure_count,
                    e,
                )

                if failure_count >= 5:
                    self._closed = True
                    raise SSEUnavailable(
                        f"SSE repeatedly failed after {failure_count} attempts",
                    )

            if self._closed:
                break

            log.debug(
                "SSE retrying in %.1fs after error (chat_id=%s)",
                backoff_seconds,
                self.chat_id,
            )
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, 30.0)

    # ------------------------------------------------------------------

    async def _read_stream(self, resp: httpx.Response) -> AsyncIterator[SSEEvent]:
        """
        Parse a single HTTP response body into SSEEvent objects.
        """
        data_lines: List[str] = []
        event_name: Optional[str] = None
        event_id: Optional[str] = None

        async for raw_line in resp.aiter_lines():
            if self._closed:
                break

            if raw_line is None:
                continue

            line = raw_line.strip("\ufeff")

            # Empty line signals dispatch
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines)
                    yield SSEEvent(
                        event=event_name or "message",
                        data=payload,
                        event_id=event_id or self._last_event_id,
                    )

                data_lines = []
                event_name = None
                event_id = None
                continue

            # Comments/keepalives begin with ':'
            if line.startswith(":"):
                continue

            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
                continue

            if line.startswith("event:"):
                event_name = line[6:].strip() or event_name
                continue

            if line.startswith("id:"):
                event_id = line[3:].strip() or event_id
                continue

            # Unknown field → ignore but keep accumulating data_lines

        # Flush any trailing data when the stream closes without a newline
        if data_lines:
            payload = "\n".join(data_lines)
            yield SSEEvent(
                event=event_name or "message",
                data=payload,
                event_id=event_id or self._last_event_id,
            )

    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        self._closed = True

        if self._client_owned:
            try:
                await self._client.aclose()
            except Exception:
                pass
