"""
Scoreboard registry scaffolding.

Responsibilities (current scope):
- Define available scoreboard types without implementing scoring math
- Register modules that can emit scoreboard-relevant events
- Provide deterministic, read-only accessors for other runtime components

All runtime scoring/enforcement remains undefined and must be implemented in
future iterations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ScoreboardModule:
    """Descriptor for a module capable of emitting scoreboard events."""

    module_id: str
    description: str
    emits: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScoreboardType:
    """Logical scoreboard definition without any scoring algorithms."""

    scoreboard_id: str
    module_id: str
    label: str
    period_kind: str = "unspecified"
    metadata: Dict[str, str] = field(default_factory=dict)


class ScoreboardRegistry:
    """
    In-memory registry for scoreboard modules and logical scoreboard types.

    This registry is intentionally declarative and contains no scoring math or
    state mutation beyond registration bookkeeping.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, ScoreboardModule] = {}
        self._scoreboards: Dict[str, ScoreboardType] = {}

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_module(self, module: ScoreboardModule) -> None:
        """
        Register a module that can emit scoreboard events.
        Existing registrations are replaced to keep the registry authoritative.
        """
        self._modules[module.module_id] = module

    def get_module(self, module_id: str) -> Optional[ScoreboardModule]:
        return self._modules.get(module_id)

    def modules(self) -> List[ScoreboardModule]:
        return list(self._modules.values())

    # ------------------------------------------------------------------
    # Scoreboard type registration
    # ------------------------------------------------------------------

    def register_scoreboard(self, scoreboard: ScoreboardType) -> None:
        """
        Register a logical scoreboard type scoped by creator and module.
        This does not perform any scoring calculations.
        """
        self._scoreboards[scoreboard.scoreboard_id] = scoreboard

    def get_scoreboard(self, scoreboard_id: str) -> Optional[ScoreboardType]:
        return self._scoreboards.get(scoreboard_id)

    def scoreboards(self) -> List[ScoreboardType]:
        return list(self._scoreboards.values())


# Authoritative, singleton-style registry for runtime components to share
scoreboard_registry = ScoreboardRegistry()
