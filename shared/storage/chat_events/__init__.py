"""Chat event storage utilities.

This package currently exposes read-only helpers for inspecting persisted chat
logs so runtime exports can derive replay availability without mutating
underlying files.
"""

from .reader import (
    CHAT_EVENT_STORAGE_ROOT,
    CHAT_LOG_ROOT,
    ReplayMetadata,
    build_replay_metadata,
)

__all__ = [
    "ReplayMetadata",
    "build_replay_metadata",
    "CHAT_EVENT_STORAGE_ROOT",
    "CHAT_LOG_ROOT",
]
