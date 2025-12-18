"""
Discord Runtime Lifecycle Utilities

This module defines lifecycle helper interfaces for the Discord
control-plane runtime.

INTENTIONAL SCAFFOLD — NO OPERATIONAL BEHAVIOR YET.

Purpose:
- Centralize lifecycle concepts (startup, ready, shutdown, health)
- Provide a stable interface for DiscordSupervisor and future dashboards
- Avoid embedding lifecycle logic inside the Discord client itself

This module does NOT:
- Start asyncio tasks
- Own the Discord client
- Perform network I/O
- Persist state directly
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime, timezone

from shared.logging.logger import get_logger

# NOTE: routed to Discord runtime log file
log = get_logger("discord.runtime.lifecycle", runtime="discord")


class DiscordRuntimeLifecycle:
    """
    Passive lifecycle state tracker for the Discord runtime.

    This class is intentionally minimal and side-effect free.
    It is designed to be:
    - owned by DiscordSupervisor
    - queried by admin / dashboard surfaces
    """

    def __init__(self):
        self._started_at: Optional[datetime] = None
        self._ready_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

    # --------------------------------------------------
    # Lifecycle Transitions (NO-OP + STATE ONLY)
    # --------------------------------------------------

    def mark_started(self):
        """
        Mark the Discord runtime as started.
        """
        if self._started_at is None:
            self._started_at = datetime.now(timezone.utc)
            log.info("Discord runtime marked as started")

    def mark_ready(self):
        """
        Mark the Discord runtime as fully ready (connected, commands loaded).
        """
        if self._ready_at is None:
            self._ready_at = datetime.now(timezone.utc)
            log.info("Discord runtime marked as ready")

    def mark_stopped(self):
        """
        Mark the Discord runtime as stopped.
        """
        self._stopped_at = datetime.now(timezone.utc)
        log.info("Discord runtime marked as stopped")

    # --------------------------------------------------
    # Introspection
    # --------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """
        Return a structured snapshot of lifecycle state.
        """
        return {
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "ready_at": self._ready_at.isoformat() if self._ready_at else None,
            "stopped_at": self._stopped_at.isoformat() if self._stopped_at else None,
        }

    @property
    def started(self) -> bool:
        return self._started_at is not None

    @property
    def ready(self) -> bool:
        return self._ready_at is not None

    @property
    def stopped(self) -> bool:
        return self._stopped_at is not None
