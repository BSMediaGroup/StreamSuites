"""
Discord Heartbeat Module (Control-Plane Runtime)

INTENTIONAL PLACEHOLDER — NO OPERATIONAL BEHAVIOR YET.

This module will be responsible for emitting periodic heartbeat signals
confirming that the Discord control-plane runtime is alive, connected,
and responsive.

Planned responsibilities:
- Emit periodic "alive" signals (dashboard, external monitor, webhook, etc.)
- Track last successful Discord connection / resume timestamp
- Provide supervisor-visible liveness state
- Support multiple heartbeat sinks (dashboard, logs, future APIs)
- Operate independently of streaming runtimes

IMPORTANT CONSTRAINTS:
- This module MUST NOT create asyncio tasks on import
- This module MUST NOT install timers or loops automatically
- This module MUST NOT own or control the Discord client
- This module MUST NOT perform network I/O directly (future adapters will)
- All scheduling must be performed by DiscordSupervisor
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from shared.logging.logger import get_logger

log = get_logger("discord.heartbeat", runtime="discord")


class DiscordHeartbeatState:
    """
    Immutable snapshot of Discord heartbeat state.

    This object is intended for:
    - dashboard serialization
    - diagnostics
    - supervisor inspection
    """

    def __init__(
        self,
        *,
        started_at: Optional[datetime] = None,
        last_tick_at: Optional[datetime] = None,
        connected: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.started_at = started_at
        self.last_tick_at = last_tick_at
        self.connected = connected
        self.metadata = metadata or {}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_tick_at": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "connected": self.connected,
            "metadata": self.metadata,
        }


class DiscordHeartbeat:
    """
    Heartbeat coordinator for the Discord control-plane runtime.

    This class is intentionally passive:
    - No timers
    - No asyncio tasks
    - No external I/O

    The supervisor is expected to:
    - call start() once
    - call tick() on a schedule
    - call stop() during shutdown
    """

    def __init__(self):
        self._started_at: Optional[datetime] = None
        self._last_tick_at: Optional[datetime] = None
        self._connected: bool = False

    # --------------------------------------------------
    # Lifecycle
    # --------------------------------------------------

    def start(self):
        """
        Mark the heartbeat as started.
        """
        if self._started_at is None:
            self._started_at = datetime.now(timezone.utc)
            log.info("Discord heartbeat started")

    def stop(self):
        """
        Mark the heartbeat as stopped.
        """
        log.info("Discord heartbeat stopped")

    # --------------------------------------------------
    # State Updates
    # --------------------------------------------------

    def set_connected(self, connected: bool):
        """
        Update Discord connection state.
        """
        self._connected = connected
        log.debug(f"Discord heartbeat connection state: {connected}")

    def tick(self):
        """
        Record a heartbeat tick.

        This does NOT emit anything externally yet.
        """
        self._last_tick_at = datetime.now(timezone.utc)
        log.debug("Discord heartbeat tick")

    # --------------------------------------------------
    # Snapshot
    # --------------------------------------------------

    def snapshot(self) -> DiscordHeartbeatState:
        """
        Return a structured snapshot of the current heartbeat state.
        """
        return DiscordHeartbeatState(
            started_at=self._started_at,
            last_tick_at=self._last_tick_at,
            connected=self._connected,
        )
