"""
Placeholder exporter for scoreboard state.

Supported formats (future): JSON and CSV.
The runtime remains the source of truth; this module will emit offline-safe
artifacts when implemented.
"""
from __future__ import annotations

from typing import Any, Dict, List


def export_scoreboards_to_json(*, creator_id: str, records: List[Dict[str, Any]]) -> str:
    """
    Export the provided scoreboard records to a JSON string.
    Implementation is intentionally deferred.
    """
    raise NotImplementedError("Scoreboard JSON export is not implemented.")


def export_scoreboards_to_csv(*, creator_id: str, records: List[Dict[str, Any]]) -> str:
    """
    Export the provided scoreboard records to a CSV string.
    Implementation is intentionally deferred.
    """
    raise NotImplementedError("Scoreboard CSV export is not implemented.")
