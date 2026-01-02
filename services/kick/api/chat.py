"""Kick chat API scaffold (runtime-authoritative)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional

from services.kick.models.message import KickChatMessage
from shared.logging.logger import get_logger

log = get_logger("kick.chat", runtime="streamsuites")


@dataclass
class KickCredentials:
    """Resolved Kick credentials loaded from environment variables."""

    client_id: str
    client_secret: str
    username: str
    channel: str

    def validate(self) -> None:
        missing = []
        if not self.client_id:
            missing.append("KICK_CLIENT_ID_DANIEL")
        if not self.client_secret:
            missing.append("KICK_CLIENT_SECRET")
        if not self.username:
            missing.append("KICK_USERNAME_DANIEL/KICK_BOT_NAME")
        if not self.channel:
            missing.append("KICK_CHANNEL")

        if missing:
            raise RuntimeError(
                "Kick credentials missing required env vars: " + ", ".join(missing)
            )


def load_env_credentials(channel_override: Optional[str] = None) -> KickCredentials:
    """
    Load Kick credentials from the runtime environment without logging secrets.

    Channel falls back to the username so workers can deterministically emit
    chat events in single-creator setups.
    """

    client_id = os.getenv("KICK_CLIENT_ID_DANIEL", "")
    client_secret = os.getenv("KICK_CLIENT_SECRET", "")
    username = os.getenv("KICK_USERNAME_DANIEL", "") or os.getenv("KICK_BOT_NAME", "")
    channel = channel_override or os.getenv("KICK_CHANNEL", "") or username

    creds = KickCredentials(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        channel=channel,
    )
    creds.validate()
    return creds


class KickChatClient:
    """
    Minimal Kick chat scaffold exposing connect() and poll().

    This client intentionally avoids network calls while still proving
    credential handling and message normalization. Synthetic messages are
    buffered at connect-time so trigger wiring can run end-to-end.
    """

    def __init__(self, *, credentials: KickCredentials) -> None:
        self.credentials = credentials
        self._connected = False
        self._token: Optional[Dict[str, str]] = None
        self._queue: asyncio.Queue[KickChatMessage] = asyncio.Queue()

    async def connect(self) -> Dict[str, str]:
        """Validate credentials and prepare a synthetic session token."""

        self.credentials.validate()
        if self._connected:
            log.debug("KickChatClient already connected; reusing session")
            return self._token or {}

        issued_at = datetime.now(timezone.utc).isoformat()
        self._token = {
            "access_token": "kick-offline-session",
            "token_type": "bearer",
            "issued_at": issued_at,
            "username": self.credentials.username,
            "channel": self.credentials.channel,
        }

        await self._seed_messages()
        self._connected = True
        log.info(
            "Kick chat session established for channel=%s (username=%s)",
            self.credentials.channel,
            self.credentials.username,
        )
        return self._token

    async def close(self) -> None:
        self._connected = False
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break
        log.info("Kick chat session closed for channel=%s", self.credentials.channel)

    async def poll(self) -> Optional[KickChatMessage]:
        """Return the next buffered message, or None if idle."""

        if not self._connected:
            raise RuntimeError("KickChatClient.poll called before connect()")

        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def iter_messages(self) -> AsyncGenerator[KickChatMessage, None]:
        """Async generator used by older worker contracts."""

        while self._connected:
            message = await self.poll()
            if message:
                yield message
                continue
            await asyncio.sleep(0.25)

    async def _seed_messages(self) -> None:
        """Populate the queue with deterministic, normalized messages."""

        synthetic_messages = [
            {
                "username": self.credentials.username or "streamsuites",
                "text": "Kick chat scaffold online",
                "user_id": "kick-system",
            },
            {
                "username": "moderator",
                "text": "!validate",
                "user_id": "kick-mod",
            },
        ]

        now = datetime.now(timezone.utc)
        for idx, raw in enumerate(synthetic_messages, start=1):
            message = KickChatMessage(
                raw=raw,
                username=raw.get("username") or "unknown",
                channel=self.credentials.channel,
                text=raw.get("text") or "",
                user_id=raw.get("user_id"),
                message_id=f"kick-{idx}",
                timestamp=now,
            )
            await self._queue.put(message)

