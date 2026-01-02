import asyncio
from typing import Optional

from core.state_exporter import runtime_state
from services.kick.api.chat import KickChatClient, load_default_session
from services.triggers.registry import TriggerRegistry
from services.triggers.validation import NonEmptyChatValidationTrigger
from services.triggers.actions import ActionExecutor
from shared.logging.logger import get_logger

log = get_logger("kick.chat_worker", runtime="streamsuites")


class KickChatWorker:
    """Scheduler-owned Kick chat worker (stubbed).

    Responsibilities:
    - Perform env-based auth handshake using the Kick stub client
    - Emit normalized chat events for trigger evaluation
    - Exercise trigger registry + action executor hooks even while offline
    """

    def __init__(self, *, ctx, channel: str, action_executor: Optional[ActionExecutor] = None):
        if not channel:
            raise RuntimeError("Kick channel is required")

        self.ctx = ctx
        self.channel = channel
        self._actions = action_executor
        self._client = KickChatClient(channel=channel, auth=load_default_session())

        self._stop_event = asyncio.Event()
        self._triggers = TriggerRegistry(creator_id=ctx.creator_id)
        self._triggers.register(NonEmptyChatValidationTrigger())

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] Kick chat worker starting (stub)")
        runtime_state.record_platform_status("kick", "connecting", creator_id=self.ctx.creator_id)

        try:
            await self._client.connect()
            runtime_state.record_platform_status("kick", "connected", creator_id=self.ctx.creator_id, success=True)

            async for message in self._client.iter_messages():
                await self._handle_message(message)
                if self._stop_event.is_set():
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            runtime_state.record_platform_error("kick", str(e), self.ctx.creator_id)
            log.warning(f"[{self.ctx.creator_id}] Kick chat worker error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        await self._client.close()
        runtime_state.record_platform_status("kick", "inactive", creator_id=self.ctx.creator_id)
        log.info(f"[{self.ctx.creator_id}] Kick chat worker stopped")

    async def _handle_message(self, message) -> None:
        event = message.to_event()
        event["creator_id"] = self.ctx.creator_id

        runtime_state.record_platform_event("kick", creator_id=self.ctx.creator_id)
        runtime_state.record_platform_heartbeat("kick")

        log.info(
            f"[{self.ctx.creator_id}] [kick:{message.channel}] "
            f"{message.username}: {message.text}"
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
