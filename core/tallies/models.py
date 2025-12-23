"""
Tallies data model (schema-only, no execution logic).

Tallies are treated as a first-class runtime concept, distinct from polls,
clips, and votes. This module defines the serializable shape for a tally
without introducing aggregation, scheduling, or trigger execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Aggregation strategies are intentionally narrow to keep parity across
# runtimes while leaving room for future customization.
TALLY_AGGREGATION_TYPES = ("weekly", "monthly", "rolling", "custom")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class TallyOption:
    """
    Atomic tally option that can be counted independently.
    """

    option_id: str
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "label": self.label,
            "metadata": self.metadata or {},
        }


@dataclass
class TallyCategory:
    """
    Optional grouping for tally options (e.g., regions, teams).
    """

    category_id: str
    label: str
    options: List[TallyOption] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> Dict[str, Any]:
        return {
            "category_id": self.category_id,
            "label": self.label,
            "options": [option.to_document() for option in self.options],
            "metadata": self.metadata or {},
        }


@dataclass
class Tally:
    """
    Read-only Tally shape for runtime awareness and future exports.

    No aggregation, scheduling, or trigger execution is performed here.
    """

    tally_id: str
    title: str
    description: Optional[str]
    creator_id: str
    aggregation_type: str = "rolling"
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    categories: List[TallyCategory] = field(default_factory=list)
    options: List[TallyOption] = field(default_factory=list)
    current_totals: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Guardrails without executing runtime logic.
        if self.aggregation_type not in TALLY_AGGREGATION_TYPES:
            # Keep the value but surface a predictable, namespaced default.
            self.aggregation_type = "custom"

    def to_document(self) -> Dict[str, Any]:
        """
        Serialize the tally for read-only export or dashboard hydration.
        """
        return {
            "tally_id": self.tally_id,
            "title": self.title,
            "description": self.description,
            "creator_id": self.creator_id,
            "aggregation_type": self.aggregation_type,
            "trigger_config": self.trigger_config or {},
            "categories": [category.to_document() for category in self.categories],
            "options": [option.to_document() for option in self.options],
            "current_totals": self.current_totals or {},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata or {},
        }
