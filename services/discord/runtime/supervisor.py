"""
Discord Runtime Supervisor

This module owns the lifecycle of the Discord control-plane runtime.
It is intentionally isolated from:
- streaming ingestion
- media processing
- platform workers (Rumble / YouTube / Twitch)

Responsibilities:
- start Discord client
- monitor connection health
- handle orderly shutdown
- provide a single async task entrypoint for Scheduler

IMPORTANT:
- This supervisor MUST be started by the Scheduler
- This supervisor MUST NOT create its own event loop
"""

import asyncio
from typing import Optional

from shared.logging.logger import get_logger
from services.discord.client import DiscordClient

log = get_logger("discord.supervisor")


class DiscordSupervisor:
    """
    Owns the Discord runtime lifecycle.

    This class is scheduler-safe:
    - start() is awaitable
    - shutdown() is idempotent
    """

    def __init__(self):
        self._client: Optional[DiscordClient] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

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
        self._task = asyncio.create_task(self._client.run())

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

        try:
            if self._client:
                await self._client.shutdown()
        except Exception as e:
            log.warning(f"Discord client shutdown error ignored: {e}")

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._client = None
        self._task = None
        self._running = False

        log.info("Discord supervisor shutdown complete")
