"""Chat event writers.

This module provides append-only writers that persist unified chat events
into durable storage (SQLite when present; JSONL fallback otherwise).
"""

from __future__ import annotations

from typing import Optional

from shared.chat.events import ChatEvent
from shared.storage.chat_events.store import append_chat_event, get_store


def write_event(event: ChatEvent, title: Optional[str] = None) -> bool:
    """Append a chat event to storage. Returns True if written."""
    return append_chat_event(event, title=title)


__all__ = ["write_event", "get_store"]
