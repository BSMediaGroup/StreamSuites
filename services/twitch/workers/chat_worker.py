import asyncio
from typing import Optional

from services.twitch.api.chat import TwitchChatClient
from services.twitch.models.message import TwitchChatMessage
from services.triggers.registry import TriggerRegistry
from services.triggers.validation import NonEmptyChatValidationTrigger
from services.triggers.actions import ActionExecutor
from shared.logging.logger import get_logger
from core.state_exporter import runtime_state

log = get_logger("twitch.chat_worker", runtime="streamsuites")


class TwitchChatWorker:
    """
    Scheduler-owned Twitch chat worker (IRC over TLS).

    Responsibilities:
    - Own the TwitchChatClient lifecycle (connect, read, send, shutdown)
    - Emit normalized chat events for future trigger routing
    - Remain cancellation-safe and free of side effects on import
    """

    def __init__(
        self,
        *,
        ctx,
        oauth_token: str,
        channel: str,
        nickname: Optional[str] = None,
        action_executor: Optional[ActionExecutor] = None,
    ):
        if not oauth_token:
            raise RuntimeError("Twitch oauth_token is required")
        if not channel:
            raise RuntimeError("Twitch channel is required")

        self.ctx = ctx
        self.channel = channel
        self.nickname = nickname or channel

        self._client = TwitchChatClient(
            token=oauth_token,
            nickname=self.nickname,
            channel=self.channel,
        )

        self._stop_event = asyncio.Event()

        # --------------------------------------------------
        # Trigger registry (per-creator, per-platform)
        # --------------------------------------------------
        self._triggers = TriggerRegistry(creator_id=ctx.creator_id)
        self._triggers.register(NonEmptyChatValidationTrigger())
        self._actions = action_executor

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker starting")
        backoff = 2.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                runtime_state.record_platform_status(
                    "twitch", "connecting", creator_id=self.ctx.creator_id
                )
                await self._client.connect()
                runtime_state.record_platform_status(
                    "twitch", "connected", creator_id=self.ctx.creator_id, success=True
                )

                async for message in self._client.iter_messages():
                    await self._handle_message(message)
                    if self._stop_event.is_set():
                        break

                if self._stop_event.is_set():
                    break

                # If we exit the loop without stop, treat as disconnect
                raise RuntimeError("Twitch connection closed; reconnecting")

            except asyncio.CancelledError:
                log.debug(f"[{self.ctx.creator_id}] Twitch chat worker cancelled")
                raise
            except Exception as e:
                runtime_state.record_platform_error("twitch", str(e), self.ctx.creator_id)
                log.warning(f"[{self.ctx.creator_id}] Twitch chat worker error: {e}")
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
            else:
                backoff = 2.0

        await self.shutdown()

    async def shutdown(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        await self._client.close()
        runtime_state.record_platform_status("twitch", "inactive", creator_id=self.ctx.creator_id)
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker stopped")

    # ------------------------------------------------------------------ #

    async def send_message(self, text: str) -> None:
        """
        Public helper for future trigger dispatchers or operators.
        """
        await self._client.send_message(text)

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: TwitchChatMessage) -> None:
        """
        Internal routing hook for chat messages.
        """
        event = message.to_event()
        event["creator_id"] = self.ctx.creator_id
        event["platform"] = "twitch"

        runtime_state.record_platform_event("twitch", creator_id=self.ctx.creator_id)
        runtime_state.record_platform_heartbeat("twitch")

        log.info(
            f"[{self.ctx.creator_id}] [#{message.channel}] "
            f"{message.username}: {message.text}"
        )

        # --------------------------------------------------
        # Trigger evaluation (no execution yet)
        # --------------------------------------------------
        actions = self._triggers.process(event)
        if actions:
            runtime_state.record_trigger_actions("twitch", len(actions), creator_id=self.ctx.creator_id)
        for action in actions:
            log.debug(
                f"[{self.ctx.creator_id}] Trigger action emitted: {action}"
            )

        if self._actions and actions:
            await self._actions.execute(actions, default_platform="twitch")

        # --------------------------------------------------
        # Built-in safety triggers (temporary)
        # --------------------------------------------------
        await self._handle_builtin_triggers(event, message)

    async def _handle_builtin_triggers(
        self,
        event: dict,
        message: TwitchChatMessage,
    ) -> None:
        """
        Minimal safety trigger for smoke testing.
        """
        text = (event.get("text") or "").strip().lower()
        if text == "!ping":
            await self.send_message("pong")
