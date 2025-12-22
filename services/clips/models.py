from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import random
import string

CLIP_STATES = (
    "queued",
    "encoding",
    "encoded",
    "uploading",
    "published",
    "failed",
)


def generate_clip_id() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=6))


def format_clip_title(
    source_title: str,
    clipper_username: str,
    clip_id: str,
    *,
    date: Optional[datetime] = None,
    max_length: int = 120,
) -> str:
    """
    Build the platform-facing clip title.

    Truncation rules:
    1) Truncate SourceLivestreamTitle first
    2) Truncate clipperUsername second
    3) Never truncate the date, "clip by", or clip_id
    """
    date = date or datetime.utcnow()
    date_str = date.strftime("%m/%d/%y")

    static_suffix = f" - {date_str} clip by "
    trailer = f" [{clip_id}]"

    remaining = max_length - len(static_suffix) - len(trailer)
    if remaining <= 0:
        # Edge case: max length too small; return minimal compliant title
        return f"{date_str} clip by {clipper_username[:max(1, max_length - len(trailer))]}{trailer}"

    # Step 1: allocate space for source title and clipper username
    source_budget = max(0, remaining - len(clipper_username))
    clipper_budget = remaining - source_budget

    truncated_source = source_title[:source_budget]
    truncated_clipper = clipper_username[:clipper_budget]

    title = f"{truncated_source}{static_suffix}{truncated_clipper}{trailer}"

    # Step 2: if still too long, trim clipper username further
    if len(title) > max_length and truncated_clipper:
        over = len(title) - max_length
        truncated_clipper = truncated_clipper[: max(0, len(truncated_clipper) - over)]
        title = f"{truncated_source}{static_suffix}{truncated_clipper}{trailer}"

    # Step 3: if still too long (extreme case), trim source title
    if len(title) > max_length and truncated_source:
        over = len(title) - max_length
        truncated_source = truncated_source[: max(0, len(truncated_source) - over)]
        title = f"{truncated_source}{static_suffix}{truncated_clipper}{trailer}"

    return title


@dataclass
class ClipDestination:
    platform: str
    channel_url: str

    @staticmethod
    def from_dict(data: Optional[Dict[str, Any]]) -> "ClipDestination":
        if not isinstance(data, dict):
            return ClipDestination(platform="rumble", channel_url="")
        return ClipDestination(
            platform=str(data.get("platform", "rumble")),
            channel_url=str(data.get("channel_url", "")),
        )


@dataclass
class ClipRequest:
    creator_id: str
    source_title: str
    clipper_username: str
    source_path: str
    start_seconds: float
    duration_seconds: float
    requested_by: Optional[str] = None
    destination_override: Optional[ClipDestination] = None
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ClipRecord:
    clip_id: str
    creator_id: str
    source_title: str
    clipper_username: str
    source_path: str
    start_seconds: float
    duration_seconds: float
    requested_at: int
    state: str
    output_path: Optional[str] = None
    published_url: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: Optional[int] = None
    requested_by: Optional[str] = None
    destination_platform: Optional[str] = None
    destination_channel_url: Optional[str] = None
    clip_title: Optional[str] = None
