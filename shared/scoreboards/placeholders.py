"""
Explicit placeholders for future scoreboard mechanics.

These functions intentionally do not contain scoring logic. They exist solely to
mark integration points for future work.
"""
from __future__ import annotations

from typing import Dict, Any


def compute_score_placeholder(event: Dict[str, Any]) -> None:
    """
    Placeholder hook for translating a detected event into a scoreboard delta.
    Runtime scoring algorithms remain undefined.
    """
    raise NotImplementedError("Score computation placeholder – no scoring logic defined.")


def merge_scoreboard_state_placeholder(state: Dict[str, Any]) -> None:
    """
    Placeholder for merging scoreboard state into persistent storage.
    No writes or merges are performed in the current scaffolding.
    """
    raise NotImplementedError("State merge placeholder – persistence not implemented.")


def resolve_paid_interaction_placeholder(event: Dict[str, Any]) -> None:
    """
    Placeholder for mapping paid interactions into scoreboard contributions.
    Detection and handling rules will be defined in future iterations.
    """
    raise NotImplementedError("Paid interaction placeholder – detection not implemented.")
