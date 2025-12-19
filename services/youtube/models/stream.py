
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class YouTubeLivestream:
    """
    Lightweight metadata carrier for a YouTube livestream.

    This is intentionally lean to keep parity with Twitch scaffolding while
    leaving room for future dashboard/state publication.
    """

    stream_id: str
    channel_id: str
    title: Optional[str] = None
    live_chat_id: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    status: str | None = None  # e.g., "live", "upcoming", "finished"

    def is_live(self) -> bool:
        return (self.status or "").lower() == "live"
