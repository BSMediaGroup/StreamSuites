import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from shared.logging.logger import get_logger

log = get_logger("rumble.chat.ingest")


class IngestFatalError(Exception):
    """Raised when the ingest stream returns a hard failure (e.g., HTTP 204)."""


@dataclass
class ChatMessage:
    user: str
    message: str
    timestamp: Optional[str] = None
    message_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class RumbleChatStreamClient:
    """Persistent chat ingest client for the authoritative Rumble endpoint."""

    STREAM_URL = "https://web7.rumble.com/chat/api/chat/{chat_id}/stream"

    def __init__(
        self,
        chat_id: str,
        *,
        client: Optional[httpx.AsyncClient] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.chat_id = str(chat_id)
        self._client = client or httpx.AsyncClient(
            headers=self._build_headers(headers),
            timeout=httpx.Timeout(10.0, read=None),
            follow_redirects=True,
        )
        self._client_owned = client is None

    def _build_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        base_headers = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://rumble.com",
        }
        if headers:
            base_headers.update(headers)
        return {k: v for k, v in base_headers.items() if v}

    async def iter_messages(self) -> AsyncIterator[ChatMessage]:
        url = self.STREAM_URL.format(chat_id=self.chat_id)
        log.info("Connecting to authoritative chat stream (chat_id=%s)", self.chat_id)

        async with self._client.stream("GET", url) as resp:
            status = resp.status_code
            if status == 204:
                raise IngestFatalError(
                    f"Chat stream returned HTTP 204 (chat_id={self.chat_id})"
                )
            if status != 200:
                body_preview = ""
                try:
                    raw = await resp.aread()
                    body_preview = raw.decode(errors="ignore")[:500]
                except Exception:
                    body_preview = "<unreadable>"
                raise IngestFatalError(
                    f"Chat stream HTTP {status} (chat_id={self.chat_id}) body={body_preview}"
                )

            async for line in resp.aiter_lines():
                if line is None:
                    continue

                stripped = line.strip()
                if not stripped:
                    continue

                for msg in self._parse_payload(stripped):
                    yield msg

    def _parse_payload(self, line: str) -> List[ChatMessage]:
        try:
            payload = json.loads(line)
        except Exception:
            log.debug("Ignoring non-JSON chat payload")
            return []

        message_blocks: List[Dict[str, Any]] = []

        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            messages = data.get("messages") if isinstance(data, dict) else None
            if isinstance(messages, list):
                message_blocks.extend([m for m in messages if isinstance(m, dict)])

            if not message_blocks and isinstance(payload.get("text"), str):
                message_blocks.append(payload)

        out: List[ChatMessage] = []
        for block in message_blocks:
            user = str(block.get("user_name") or block.get("username") or "").strip()
            text = str(block.get("text") or "").strip()
            if not user or not text:
                continue

            timestamp = None
            for ts_field in ("created_on", "created_at", "timestamp"):
                raw_ts = block.get(ts_field)
                if raw_ts is not None:
                    timestamp = str(raw_ts)
                    break

            message_id = None
            for id_field in ("message_id", "id"):
                raw_id = block.get(id_field)
                if raw_id is not None:
                    message_id = str(raw_id)
                    break

            out.append(
                ChatMessage(
                    user=user,
                    message=text,
                    timestamp=timestamp,
                    message_id=message_id,
                    raw=block,
                )
            )

        return out

    async def aclose(self) -> None:
        if self._client_owned:
            try:
                await self._client.aclose()
            except Exception:
                pass
