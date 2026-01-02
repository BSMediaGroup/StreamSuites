from __future__ import annotations

import asyncio
from typing import Dict, Optional

from core.state_exporter import runtime_state
from core.state_exporter import runtime_snapshot_exporter
from services.kick.api.chat import KickChatClient, load_env_credentials
from services.triggers.actions import ActionExecutor
from services.triggers.registry import TriggerRegistry
from services.triggers.validation import NonEmptyChatValidationTrigger
from shared.logging.logger import get_logger

log = get_logger("kick.chat_worker", runtime="streamsuites")


class KickChatWorker:
    """Scheduler-owned Kick chat worker."""

    def __init__(
        self,
        *,
        ctx,
        channel: str,
        action_executor: Optional[ActionExecutor] = None,
    ) -> None:
        if not channel:
            raise RuntimeError("Kick channel is required")

        self.ctx = ctx
        self.channel = channel
        self._actions = action_executor
        self._client = KickChatClient(credentials=load_env_credentials(channel))

        self._stop_event = asyncio.Event()
        self._triggers = TriggerRegistry(creator_id=ctx.creator_id)
        self._triggers.register(NonEmptyChatValidationTrigger())

    async def run(self) -> None:
        runtime_state.record_platform_status(
            "kick", "connecting", creator_id=self.ctx.creator_id
        )
        try:
            await self._client.connect()
            runtime_state.record_platform_status(
                "kick", "connected", creator_id=self.ctx.creator_id, success=True
            )

            while not self._stop_event.is_set():
                message = await self._client.poll()
                if message:
                    await self._handle_message(message)
                    continue
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            runtime_state.record_platform_error("kick", str(exc), self.ctx.creator_id)
            log.warning(f"[{self.ctx.creator_id}] Kick chat worker error: {exc}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        await self._client.close()
        runtime_state.record_platform_status("kick", "inactive", creator_id=self.ctx.creator_id)
        log.info(f"[{self.ctx.creator_id}] Kick chat worker stopped")

    async def _handle_message(self, message: Dict) -> None:
        event = dict(message)
        event.setdefault("platform", "kick")
        event["creator_id"] = self.ctx.creator_id

        runtime_state.record_platform_event("kick", creator_id=self.ctx.creator_id)
        runtime_state.record_platform_heartbeat("kick")

        log.info(
            f"[{self.ctx.creator_id}] [kick:{event.get('channel')}] "
            f"{event.get('user', {}).get('name')}: {event.get('text')}"
        )

        actions = self._triggers.process(event)
        if actions:
            runtime_state.record_trigger_actions("kick", len(actions), creator_id=self.ctx.creator_id)
            for action in actions:
                log.debug(
                    f"[{self.ctx.creator_id}] Kick trigger action emitted: {action}"
                )

        if self._actions and actions:
            await self._actions.execute(actions, default_platform="kick")

        # Publish updated counters so trigger activity is visible without logs
        try:
            runtime_snapshot_exporter.publish()
        except Exception:
            log.debug("Runtime snapshot publish skipped for kick message")


__all__ = ["KickChatWorker"]

