"""Chat event storage utilities."""

from .reader import (
    CHAT_EVENT_STORAGE_ROOT,
    CHAT_LOG_ROOT,
    ReplayMetadata,
    build_replay_metadata,
)
from .store import (
    append_chat_event,
    get_store,
    get_stream,
    list_streams,
    paginate_events,
    range_events,
    tail_events,
)

__all__ = [
    "ReplayMetadata",
    "build_replay_metadata",
    "CHAT_EVENT_STORAGE_ROOT",
    "CHAT_LOG_ROOT",
    "append_chat_event",
    "get_store",
    "get_stream",
    "list_streams",
    "paginate_events",
    "range_events",
    "tail_events",
]
