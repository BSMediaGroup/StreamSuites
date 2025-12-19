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
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any

from shared.logging.logger import get_logger
from services.discord.client import DiscordClient
from services.discord.status import DiscordStatusManager
from services.discord.heartbeat import DiscordHeartbeat, DiscordHeartbeatState

# NOTE: routed to Discord runtime log file
log = get_logger("discord.supervisor", runtime="discord")


class DiscordSnapshotWriter:
    """
    Atomic JSON snapshot writer for Discord runtime state.

    Owned exclusively by the DiscordSupervisor to guarantee a single
    authoritative output for dashboard consumption.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else Path("shared/state/discord/runtime.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: Dict[str, Any]) -> None:
        """
        Persist a snapshot atomically to avoid partial reads by consumers.
        """
        try:
            serialized = json.dumps(payload, indent=2)
            with tempfile.NamedTemporaryFile(
                "w", dir=self._path.parent, delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(serialized)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_path = Path(tmp.name)

            temp_path.replace(self._path)
        except Exception as e:
            log.error(f"Failed to write Discord runtime snapshot: {e}")


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
        self._guild_count: Optional[int] = None

        self._status = DiscordStatusManager()
        self._heartbeat = DiscordHeartbeat()
        self._snapshot_writer = DiscordSnapshotWriter()

    # --------------------------------------------------
    # Snapshot helpers (supervisor-owned)
    # --------------------------------------------------

    def _refresh_guild_count(self):
        bot = self._client.bot if self._client and self._client.bot else None
        self._guild_count = len(bot.guilds) if bot else None

    def _build_snapshot_payload(self) -> Dict[str, Any]:
        self._refresh_guild_count()
        heartbeat_state = self.heartbeat

        return {
            "running": self._running,
            "connected": self.connected,
            "last_heartbeat_ts": (
                heartbeat_state.last_tick_at.isoformat()
                if heartbeat_state.last_tick_at
                else None
            ),
            "task_count": self.task_count,
            "tasks": self.task_count,  # backward-compatible alias
            "guild_count": self._guild_count if self.connected else None,
            "status": self.status,
            "heartbeat": heartbeat_state.snapshot(),
        }

    def _write_snapshot(self):
        self._snapshot_writer.write(self._build_snapshot_payload())

    def notify_connected(self):
        self._heartbeat.set_connected(True)
        self._refresh_guild_count()
        self._write_snapshot()

    def notify_disconnected(self):
        self._heartbeat.set_connected(False)
        self._refresh_guild_count()
        self._write_snapshot()

    def notify_heartbeat_tick(self):
        self._write_snapshot()

    # --------------------------------------------------
    # Lifecycle
    # --------------------------------------------------

    async def start(self):
        """
        Start the Discord runtime.
        """
        if self._running:
            log.warning("Discord supervisor already running")
            return

        log.info("Starting Discord supervisor")

        self._client = DiscordClient(supervisor=self)

        # --------------------------------------------------
        # Heartbeat lifecycle start
        # --------------------------------------------------
        self._heartbeat.start()

        # --------------------------------------------------
        # Discord client main loop
        # --------------------------------------------------
        client_task = asyncio.create_task(self._client.run())
        self._tasks.append(client_task)

        # --------------------------------------------------
        # Post-ready initialization (status + heartbeat)
        # --------------------------------------------------
        async def _post_ready_init():
            try:
                await self._client._ready_event.wait()
                bot = self._client.bot
                if bot:
                    self.notify_connected()
                    await self._status.apply(bot)
                    log.info("Discord status applied by supervisor")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning(f"Post-ready Discord init failed: {e}")

        init_task = asyncio.create_task(_post_ready_init())
        self._tasks.append(init_task)

        # --------------------------------------------------
        # Heartbeat tick loop (supervisor-owned)
        # --------------------------------------------------
        async def _heartbeat_loop():
            try:
                while True:
                    self._heartbeat.tick()
                    self.notify_heartbeat_tick()
                    await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise

        self._tasks.append(asyncio.create_task(_heartbeat_loop()))

        self._running = True
        log.info("Discord supervisor started")
        self._write_snapshot()

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------

    async def shutdown(self):
        """
        Gracefully shut down the Discord runtime.
        """
        if not self._running:
            return

        log.info("Shutting down Discord supervisor")

        # --------------------------------------------------
        # Heartbeat shutdown
        # --------------------------------------------------
        self.notify_disconnected()
        self._heartbeat.stop()

        # --------------------------------------------------
        # Stop Discord client first
        # --------------------------------------------------
        try:
            if self._client:
                await self._client.shutdown()
        except Exception as e:
            log.warning(f"Discord client shutdown error ignored: {e}")

        # --------------------------------------------------
        # Cancel remaining tasks
        # --------------------------------------------------
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

        self._write_snapshot()

        log.info("Discord supervisor shutdown complete")

    # --------------------------------------------------
    # Read-only Introspection (NEW — SAFE)
    # --------------------------------------------------

    @property
    def running(self) -> bool:
        """
        Whether the Discord runtime is currently running.
        """
        return self._running

    @property
    def heartbeat(self) -> DiscordHeartbeatState:
        """
        Snapshot of the current Discord heartbeat state.
        """
        return self._heartbeat.snapshot()

    @property
    def status(self) -> Dict[str, Any]:
        """
        Snapshot of the current Discord presence state.
        """
        return self._status.snapshot()

    @property
    def connected(self) -> bool:
        """
        Whether the Discord client is currently connected.
        """
        return self.heartbeat.connected

    @property
    def task_count(self) -> int:
        """
        Number of supervisor-owned asyncio tasks.
        """
        return len(self._tasks)

    def snapshot(self) -> Dict[str, Any]:
        """
        Full supervisor state snapshot for diagnostics / dashboard use.
        """
        return self._build_snapshot_payload()
