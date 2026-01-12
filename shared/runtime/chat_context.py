"""Runtime active chat context tracking."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Optional


@dataclass
class ActiveChatContext:
    mode: str = "none"  # none | live | replay
    stream_id: Optional[str] = None
    live_stream_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "stream_id": self.stream_id,
            "live_stream_id": self.live_stream_id,
        }


_LOCK = Lock()
_CONTEXT = ActiveChatContext()


def get_context() -> ActiveChatContext:
    with _LOCK:
        return ActiveChatContext(
            mode=_CONTEXT.mode,
            stream_id=_CONTEXT.stream_id,
            live_stream_id=_CONTEXT.live_stream_id,
        )


def update_live_stream(stream_id: str) -> Optional[str]:
    """Record the currently active live stream id. Returns the previous id."""
    previous = None
    if not stream_id:
        return previous
    with _LOCK:
        previous = _CONTEXT.live_stream_id
        _CONTEXT.live_stream_id = stream_id
        if _CONTEXT.mode == "none":
            _CONTEXT.mode = "live"
            _CONTEXT.stream_id = stream_id
        elif _CONTEXT.mode == "live":
            _CONTEXT.stream_id = stream_id
    return previous


def select_replay(stream_id: str) -> ActiveChatContext:
    if not stream_id:
        raise ValueError("stream_id is required")
    with _LOCK:
        _CONTEXT.mode = "replay"
        _CONTEXT.stream_id = stream_id
        return get_context()


def clear_replay() -> ActiveChatContext:
    with _LOCK:
        if _CONTEXT.live_stream_id:
            _CONTEXT.mode = "live"
            _CONTEXT.stream_id = _CONTEXT.live_stream_id
        else:
            _CONTEXT.mode = "none"
            _CONTEXT.stream_id = None
        return get_context()


def set_none() -> ActiveChatContext:
    with _LOCK:
        _CONTEXT.mode = "none"
        _CONTEXT.stream_id = None
        return get_context()


__all__ = [
    "ActiveChatContext",
    "get_context",
    "update_live_stream",
    "select_replay",
    "clear_replay",
    "set_none",
]
