"""
Read-only poll export scaffolding.

This module defines the public poll summary shape (question, options, and
aggregated results only) without introducing voting or mutation logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

PUBLIC_POLL_STATUSES = ("draft", "open", "closed", "archived")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_iso8601(timestamp: Any) -> str:
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(timestamp, str):
        return timestamp
    return _utc_now()


@dataclass
class PublicPollOptionResult:
    """
    Aggregated, read-only poll option result.
    """

    option_id: str
    label: str
    votes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "option_id": self.option_id,
            "label": self.label,
            "votes": int(self.votes),
            "metadata": self.metadata or {},
        }
        return doc


@dataclass
class PublicPollSummary:
    """
    Serializable poll summary suitable for public gallery consumption.
    """

    poll_id: str
    question: str
    creator_name: str
    status: str
    options: List[PublicPollOptionResult]
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        return {
            "poll_id": self.poll_id,
            "question": self.question,
            "creator_name": self.creator_name,
            "status": self.status,
            "options": [option.to_document() for option in self.options],
            "created_at": self.created_at,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(
        cls,
        payload: Dict[str, Any],
        *,
        creator_name: str,
        option_key: str = "options",
    ) -> "PublicPollSummary":
        """
        Build a public poll summary from a mapping without mutating it.

        The option_key argument allows callers to map existing payload shapes
        into the public export structure while keeping aggregation read-only.
        """
        poll_id = payload.get("poll_id") or payload.get("id") or ""
        question = payload.get("question") or payload.get("title") or ""
        status = payload.get("status") or payload.get("state") or "draft"
        created_at = payload.get("created_at") or payload.get("createdAt")

        options_payload = payload.get(option_key) or []
        options: List[PublicPollOptionResult] = []
        if isinstance(options_payload, list):
            for option in options_payload:
                if not isinstance(option, dict):
                    continue
                option_id = option.get("option_id") or option.get("id") or option.get("value") or ""
                label = option.get("label") or option.get("text") or ""
                votes = int(option.get("votes", 0))
                metadata = option.get("metadata", {}) or {}
                options.append(
                    PublicPollOptionResult(
                        option_id=str(option_id),
                        label=str(label),
                        votes=votes,
                        metadata=metadata,
                    )
                )

        metadata = payload.get("metadata", {}) or {}

        return cls(
            poll_id=str(poll_id),
            question=str(question),
            creator_name=str(creator_name),
            status=str(status),
            options=options,
            created_at=_coerce_iso8601(created_at),
            metadata=metadata,
        )


@dataclass
class PublicPollExport:
    """
    Container for a public poll export document.
    """

    schema_version: str = "v1"
    generated_at: str = field(default_factory=_utc_now)
    polls: List[PublicPollSummary] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "polls": [poll.to_document() for poll in self.polls],
        }


class PublicPollExportBuilder:
    """
    Convenience builder that assembles the public poll snapshot shape.
    """

    def __init__(self, *, schema_version: str = "v1") -> None:
        self.schema_version = schema_version

    def build(self, polls: Iterable[PublicPollSummary]) -> Dict[str, Any]:
        export = PublicPollExport(
            schema_version=self.schema_version,
            polls=list(polls),
        )
        return export.to_document()
