"""Stream index helpers for chat replay lookup."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.storage.chat_events.store import get_store


def list_streams() -> List[Dict[str, Any]]:
    return get_store().list_streams()


def get_stream(stream_id: str) -> Optional[Dict[str, Any]]:
    return get_store().get_stream(stream_id)


def mark_stream_ended(stream_id: str, ts: str) -> None:
    get_store().mark_stream_ended(stream_id, ts)


__all__ = ["list_streams", "get_stream", "mark_stream_ended"]
