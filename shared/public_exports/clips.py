"""
Read-only clip export scaffolding.

This module defines the minimal public-facing clip shape for future gallery
consumers without exposing internal runtime fields. No HTTP wiring is
performed here; callers are expected to build snapshots and write them to a
static export location when appropriate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

PUBLIC_CLIP_STATES = ("pending", "encoding", "published")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_iso8601(timestamp: Any) -> str:
    """
    Normalize timestamps into an ISO-8601 string.

    The clip runtime stores timestamps as integers (epoch seconds). This helper
    accepts either integers or preformatted strings to avoid coupling the
    public export surface to the persistence layer.
    """
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(timestamp, str):
        return timestamp
    return _utc_now()


def _map_clip_state(state: Optional[str]) -> str:
    """
    Map internal clip states into the public gallery surface.

    - queued → pending
    - encoding/encoded/uploading → encoding
    - published → published
    - failed/unknown → pending (retryable/placeholder)
    """
    normalized = (state or "").lower()

    if normalized in ("queued", "requested"):
        return "pending"
    if normalized in ("encoding", "encoded", "uploading"):
        return "encoding"
    if normalized == "published":
        return "published"

    return "pending"


@dataclass
class PublicClipSummary:
    """
    Serializable, read-only clip summary suitable for public display.
    """

    clip_id: str
    title: str
    creator_name: str
    platform: str
    destination_url: str
    state: str
    created_at: str
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "clip_id": self.clip_id,
            "title": self.title,
            "creator_name": self.creator_name,
            "platform": self.platform,
            "destination_url": self.destination_url,
            "state": self.state,
            "created_at": self.created_at,
            "metadata": self.metadata or {},
        }

        if self.thumbnail_url:
            doc["thumbnail_url"] = self.thumbnail_url

        return doc

    @classmethod
    def from_clip_record(
        cls,
        clip_record: Any,
        *,
        creator_name: str,
        thumbnail_url: Optional[str] = None,
        destination_url: Optional[str] = None,
    ) -> "PublicClipSummary":
        """
        Build a public summary from an internal clip record without mutating it.

        The `clip_record` argument accepts either a dataclass or mapping with
        the clip runtime's fields. Unknown fields are ignored to keep the
        export surface stable.
        """
        clip_id = getattr(clip_record, "clip_id", None) or (clip_record.get("clip_id") if isinstance(clip_record, dict) else "")
        title = getattr(clip_record, "clip_title", None) or (
            clip_record.get("clip_title") if isinstance(clip_record, dict) else None
        )
        source_title = getattr(clip_record, "source_title", None) or (
            clip_record.get("source_title") if isinstance(clip_record, dict) else ""
        )
        resolved_title = title or source_title or f"Clip {clip_id}".strip()

        internal_state = getattr(clip_record, "state", None) or (clip_record.get("state") if isinstance(clip_record, dict) else None)
        public_state = _map_clip_state(internal_state)

        created_at = getattr(clip_record, "requested_at", None) or (
            clip_record.get("requested_at") if isinstance(clip_record, dict) else None
        )

        platform = getattr(clip_record, "destination_platform", None) or (
            clip_record.get("destination_platform") if isinstance(clip_record, dict) else None
        )
        platform = platform or "unknown"

        published_url = getattr(clip_record, "published_url", None) or (
            clip_record.get("published_url") if isinstance(clip_record, dict) else None
        )
        resolved_destination = destination_url or published_url or getattr(clip_record, "destination_channel_url", None) or ""

        metadata = {}
        requested_by = getattr(clip_record, "requested_by", None) or (
            clip_record.get("requested_by") if isinstance(clip_record, dict) else None
        )
        if requested_by:
            metadata["requested_by"] = requested_by

        return cls(
            clip_id=str(clip_id),
            title=str(resolved_title),
            creator_name=str(creator_name),
            platform=str(platform),
            destination_url=str(resolved_destination),
            state=public_state,
            created_at=_coerce_iso8601(created_at),
            thumbnail_url=thumbnail_url,
            metadata=metadata,
        )


@dataclass
class PublicClipExport:
    """
    Container for a public clip export document.
    """

    schema_version: str = "v1"
    generated_at: str = field(default_factory=_utc_now)
    clips: List[PublicClipSummary] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "clips": [clip.to_document() for clip in self.clips],
        }


class PublicClipExportBuilder:
    """
    Convenience builder that assembles the public clip snapshot shape.
    """

    def __init__(self, *, schema_version: str = "v1") -> None:
        self.schema_version = schema_version

    def build(self, clips: Iterable[PublicClipSummary]) -> Dict[str, Any]:
        export = PublicClipExport(
            schema_version=self.schema_version,
            clips=list(clips),
        )
        return export.to_document()
