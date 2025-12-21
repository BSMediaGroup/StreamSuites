"""
Placeholder importer for scoreboard state.

Supported formats (future): JSON and CSV.
Offline uploads or admin-triggered imports will be added when policies exist.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable


def import_scoreboards_from_json(*, creator_id: str, payload: str) -> Iterable[Dict[str, Any]]:
    """
    Parse a JSON payload and yield scoreboard rows.
    Implementation is intentionally deferred.
    """
    raise NotImplementedError("Scoreboard JSON import is not implemented.")


def import_scoreboards_from_csv(*, creator_id: str, payload: str) -> Iterable[Dict[str, Any]]:
    """
    Parse a CSV payload and yield scoreboard rows.
    Implementation is intentionally deferred.
    """
    raise NotImplementedError("Scoreboard CSV import is not implemented.")
