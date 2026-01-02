import asyncio
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

from services.kick.models.message import KickChatMessage
from shared.logging.logger import get_logger

log = get_logger("kick.chat", runtime="streamsuites")


class KickAuthSession:
    """Stubbed auth handshake for Kick.

    The runtime already carries Kick env vars. This stub only verifies their
    presence and produces a placeholder token payload so downstream workers can
    prove wiring without emitting secrets.
    """

    def __init__(self, *, client_id: str, client_secret: str, username: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username

    def perform_handshake(self) -> Dict[str, str]:
        if not all([self.client_id, self.client_secret, self.username]):
            raise RuntimeError("Kick credentials are incomplete; cannot handshake")

        # Placeholder token payload; no network calls are performed.
        return {
            "access_token": "stub-kick-token",
            "token_type": "bearer",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "username": self.username,
        }


class KickChatClient:
    """Simulated Kick chat client.

    The implementation mirrors Twitch/YouTube interfaces while staying offline.
    Callers can iterate over a deterministic, synthetic message stream to prove
    trigger wiring end-to-end.
    """

    def __init__(self, *, channel: str, auth: KickAuthSession):
        self.channel = channel
        self.auth = auth
        self._connected = False
        self._token: Optional[Dict[str, str]] = None

    async def connect(self) -> None:
        if self._connected:
            log.debug("KickChatClient already connected")
            return

        self._token = self.auth.perform_handshake()
        log.info(
            f"Connecting to Kick chat (stub) as {self._token['username']} on channel={self.channel}"
        )
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        log.info("Kick chat stub connection closed")

    async def iter_messages(self) -> AsyncGenerator[KickChatMessage, None]:
        if not self._connected:
            raise RuntimeError("KickChatClient.iter_messages called before connect()")

        # Deterministic synthetic message set proves normalization + trigger wiring.
        synthetic_messages = [
            {"username": "StreamSuites", "text": "Kick stub online", "user_id": "kick-1"},
            {"username": "Moderator", "text": "!validate", "user_id": "kick-2"},
        ]

        for raw in synthetic_messages:
            yield self._normalize(raw)
            await asyncio.sleep(0)

    def _normalize(self, raw: Dict[str, Any]) -> KickChatMessage:
        timestamp = datetime.now(timezone.utc)
        message = KickChatMessage(
            raw=raw,
            username=raw.get("username") or "unknown",
            channel=self.channel,
            text=raw.get("text") or "",
            user_id=raw.get("user_id"),
            timestamp=timestamp,
        )
        log.debug(f"[kick:{self.channel}] normalized stub message: {message.text}")
        return message


def load_default_session() -> KickAuthSession:
    """Factory that reads env vars without logging secrets."""

    client_id = os.getenv("KICK_CLIENT_ID_DANIEL", "")
    client_secret = os.getenv("KICK_CLIENT_SECRET", "")
    username = os.getenv("KICK_USERNAME_DANIEL", "") or os.getenv("KICK_BOT_NAME", "")

    return KickAuthSession(client_id=client_id, client_secret=client_secret, username=username)
