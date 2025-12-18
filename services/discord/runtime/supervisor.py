"""
Discord Runtime Supervisor

Owns the lifecycle of the Discord control-plane runtime.

This supervisor is:
- scheduler-owned
- event-loop agnostic
- safe to run alongside streaming runtimes

Responsibilities:
- start Discord client
- manage background Discord tasks (status, heartbeat)
- perform graceful shutdown

IMPORTANT:
- MUST be started by core.scheduler
- MUST NOT create its own event loop
- MUST NOT install signal handlers
"""

from __future__ import annotations

import asyncio
from typing import Optional, List

from shared.logging.logger import get_logger
from services.discord.client import DiscordClient
from services.discord.status import DiscordStatusManager

log = get_logger("discord.supervisor")


class DiscordSupervisor:
    """
    Owns the Discord runtime lifecycle.

    Scheduler-safe contract:
    - start() is awaitable
    - shutdown() is idempotent
    """

    def __init__(self):
        self._client: Optional[DiscordClient] = None
        self._tasks: List[asyncio.Task] = []
        self._running: bool = False

        self._status = DiscordStatusManager()

    # --------------------------------------------------

    async def start(self):
        """
        Start the Discord runtime.
        """
        if self._running:
            log.warning("Discord supervisor already running")
            return

        log.info("Starting Discord supervisor")

        self._client = DiscordClient()

        # Discord client main loop
        client_task = asyncio.create_task(self._client.run())
        self._tasks.append(client_task)

        self._running = True
        log.info("Discord supervisor started")

    # --------------------------------------------------

    async def shutdown(self):
        """
        Gracefully shut down the Discord runtime.
        """
        if not self._running:
            return

        log.info("Shutting down Discord supervisor")

        # Stop Discord client first
        try:
            if self._client:
                await self._client.shutdown()
        except Exception as e:
            log.warning(f"Discord client shutdown error ignored: {e}")

        # Cancel remaining tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(
                *self._tasks,
                return_exceptions=True
            )

        self._tasks.clear()
        self._client = None
        self._running = False

        log.info("Discord supervisor shutdown complete")
