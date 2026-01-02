"""Kick chat API scaffold (runtime-authoritative)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional, Tuple

from services.kick.models.message import KickChatMessage
from shared.logging.logger import get_logger

log = get_logger("kick.chat", runtime="streamsuites")


def _normalize_suffix(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    sanitized = "".join(ch if ch.isalnum() else "_" for ch in value)
    return sanitized.upper()


def _resolve_env(prefix: str, channel_hint: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    candidates = {k: v for k, v in os.environ.items() if k.startswith(prefix)}
    preferred_key = None
    if channel_hint:
        normalized = _normalize_suffix(channel_hint)
        if normalized:
            preferred_key = f"{prefix}{normalized}"
    if preferred_key and preferred_key in candidates and candidates[preferred_key]:
        return candidates[preferred_key], preferred_key
    if len(candidates) == 1:
        key = next(iter(candidates))
        return candidates[key], key
    return None, preferred_key


@dataclass
class KickCredentials:
    """Resolved Kick credentials loaded from environment variables."""

    client_id: str
    client_secret: str
    username: str
    channel: str
    resolved_keys: Dict[str, Optional[str]]

    def validate(self) -> None:
        missing = []
        if not self.client_id:
            missing.append(self.resolved_keys.get("client_id") or "KICK_CLIENT_ID_*")
        if not self.client_secret:
            missing.append(
                self.resolved_keys.get("client_secret") or "KICK_CLIENT_SECRET_*"
            )
        if not self.username:
            missing.append(
                self.resolved_keys.get("username") or "KICK_USERNAME_*/KICK_BOT_NAME"
            )
        if not self.channel:
            missing.append("KICK_CHANNEL/KICK_USERNAME_*/KICK_BOT_NAME")

        if missing:
            raise RuntimeError(
                "Kick credentials missing required env vars: " + ", ".join(missing)
            )


def load_env_credentials(channel_override: Optional[str] = None) -> KickCredentials:
    """
    Load Kick credentials from the runtime environment without logging secrets.

    Env keys are matched using wildcard prefixes so multiple creators can be
    provisioned concurrently (e.g., KICK_CLIENT_ID_DANIEL, KICK_CLIENT_ID_STAGING).
    """

    channel_hint = channel_override or os.getenv("KICK_CHANNEL")
    client_id, client_id_key = _resolve_env("KICK_CLIENT_ID_", channel_hint)
    if not client_id:
        fallback_id = os.getenv("KICK_CLIENT_ID")
        if fallback_id:
            client_id = fallback_id
            client_id_key = "KICK_CLIENT_ID"
    client_secret, client_secret_key = _resolve_env(
        "KICK_CLIENT_SECRET_", channel_hint
    )
    if not client_secret:
        fallback_secret = os.getenv("KICK_CLIENT_SECRET")
        if fallback_secret:
            client_secret = fallback_secret
            client_secret_key = "KICK_CLIENT_SECRET"
    username, username_key = _resolve_env("KICK_USERNAME_", channel_hint)
    if not username:
        fallback_username = os.getenv("KICK_USERNAME")
        if fallback_username:
            username = fallback_username
            username_key = "KICK_USERNAME"

    if not username:
        username = os.getenv("KICK_BOT_NAME", "")
        username_key = username_key or "KICK_BOT_NAME"

    channel = channel_override or os.getenv("KICK_CHANNEL", "") or username

    creds = KickCredentials(
        client_id=client_id or "",
        client_secret=client_secret or "",
        username=username or "",
        channel=channel or "",
        resolved_keys={
            "client_id": client_id_key,
            "client_secret": client_secret_key,
            "username": username_key,
        },
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

    async def poll(self) -> Optional[Dict[str, object]]:
        """Return the next normalized chat event, or None if idle."""

        if not self._connected:
            raise RuntimeError("KickChatClient.poll called before connect()")

        try:
            message = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        return message.to_event()

    async def iter_messages(self) -> AsyncGenerator[Dict[str, object], None]:
        """Async generator returning normalized chat events."""

        while self._connected:
            event = await self.poll()
            if event:
                yield event
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

