"""
Scoreboard snapshot helpers (read-only).

This module builds schema-aligned JSON documents for dashboard consumption
without mutating runtime state or defining scoring logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ScoreboardEntry:
    """Serializable scoreboard row with no scoring math."""

    module_id: str
    user_id: str
    display_name: str
    score_value: float | int
    metadata: Dict[str, Any] = field(default_factory=dict)
    period: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_event_at: Optional[str] = None

    def to_document(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "module_id": self.module_id,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "score_value": self.score_value,
            "metadata": self.metadata or {},
        }

        if self.period:
            doc["period"] = self.period
        if self.created_at:
            doc["created_at"] = self.created_at
        if self.updated_at:
            doc["updated_at"] = self.updated_at
        if self.last_event_at:
            doc["last_event_at"] = self.last_event_at

        return doc


@dataclass
class ScoreboardSnapshot:
    """
    Read-only scoreboard snapshot scoped to a creator.

    All aggregation logic is out-of-scope for this scaffolding.
    """

    creator_id: str
    schema_version: str = "v1"
    generated_at: str = field(default_factory=_utc_now)
    period: Optional[Dict[str, Any]] = None
    entries: List[ScoreboardEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "creator_id": self.creator_id,
            "entries": [entry.to_document() for entry in self.entries],
        }

        if self.period:
            doc["period"] = self.period

        if self.metadata:
            doc["metadata"] = self.metadata

        return doc


class ScoreboardSnapshotBuilder:
    """
    Convenience builder for assembling snapshots without performing any math.
    """

    def __init__(self, *, schema_version: str = "v1") -> None:
        self.schema_version = schema_version

    def build(
        self,
        *,
        creator_id: str,
        entries: Optional[List[ScoreboardEntry]] = None,
        period: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        snapshot = ScoreboardSnapshot(
            creator_id=creator_id,
            schema_version=self.schema_version,
            period=period,
            entries=entries or [],
            metadata=metadata or {},
        )
        return snapshot.to_document()
