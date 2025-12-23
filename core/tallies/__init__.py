"""
Tallies package.

This namespace currently exposes schema/dataclass definitions only.
Execution, aggregation, scheduling, and trigger handling are intentionally
deferred to keep tallies isolated from polls, clips, and votes.
"""

from .models import (
    TALLY_AGGREGATION_TYPES,
    Tally,
    TallyCategory,
    TallyOption,
)

__all__ = [
    "TALLY_AGGREGATION_TYPES",
    "Tally",
    "TallyCategory",
    "TallyOption",
]
