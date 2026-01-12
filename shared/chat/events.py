"""Canonical unified chat event schema and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

SUPPORTED_PLATFORMS = {
    "rumble",
    "youtube",
    "twitch",
    "discord",
    "kick",
    "pilled",
    "streamsuites",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_iso(ts: Optional[str]) -> str:
    if not ts:
        return _utc_now_iso()
    if isinstance(ts, str) and ts.endswith("Z"):
        return ts
    try:
        parsed = datetime.fromisoformat(ts)
    except Exception:
        return _utc_now_iso()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_platform(value: str) -> str:
    platform = (value or "").lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"Unsupported source_platform: {value}")
    return platform


@dataclass
class ChatAuthor:
    author_id: str
    display_name: str
    avatar_url: Optional[str] = None
    badges: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)


@dataclass
class ChatContent:
    type: str
    text: str


@dataclass
class ChatFlags:
    is_synthetic: bool = False
    is_system: bool = False
    is_highlighted: bool = False


@dataclass
class ChatEvent:
    event_id: str
    ts: str
    stream_id: str
    source_platform: str
    author: ChatAuthor
    content: ChatContent
    flags: ChatFlags
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.raw is None:
            payload.pop("raw", None)
        return payload


def create_chat_event(
    *,
    stream_id: str,
    source_platform: str,
    author_id: str,
    display_name: str,
    text: str,
    avatar_url: Optional[str] = None,
    badges: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    is_synthetic: bool = False,
    is_system: bool = False,
    is_highlighted: bool = False,
    raw: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> ChatEvent:
    if not stream_id:
        raise ValueError("stream_id is required")
    if not display_name:
        raise ValueError("display_name is required")
    if not text:
        raise ValueError("content text is required")

    platform = normalize_platform(source_platform)

    author = ChatAuthor(
        author_id=str(author_id or ""),
        display_name=str(display_name),
        avatar_url=avatar_url,
        badges=list(badges or []),
        roles=list(roles or []),
    )
    content = ChatContent(type="message", text=str(text))
    flags = ChatFlags(
        is_synthetic=bool(is_synthetic),
        is_system=bool(is_system),
        is_highlighted=bool(is_highlighted),
    )
    event = ChatEvent(
        event_id=event_id or str(uuid4()),
        ts=_normalize_iso(ts),
        stream_id=str(stream_id),
        source_platform=platform,
        author=author,
        content=content,
        flags=flags,
        raw=raw,
    )
    return event


__all__ = [
    "ChatAuthor",
    "ChatContent",
    "ChatFlags",
    "ChatEvent",
    "SUPPORTED_PLATFORMS",
    "create_chat_event",
    "normalize_platform",
]
