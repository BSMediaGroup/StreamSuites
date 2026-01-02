import asyncio
from typing import Optional

from services.youtube.api.chat import YouTubeChatClient
from services.youtube.models.message import YouTubeChatMessage
from services.triggers.registry import TriggerRegistry
from services.triggers.validation import NonEmptyChatValidationTrigger
from services.triggers.actions import ActionExecutor
from shared.logging.logger import get_logger
from core.state_exporter import runtime_state, runtime_snapshot_exporter

from shared.runtime.quotas import (
    quota_registry,
    QuotaExceeded,
    QuotaBufferWarning,
)


log = get_logger("youtube.chat_worker", runtime="streamsuites")


class YouTubeChatWorker:
    """
    Scheduler-owned YouTube chat worker (polling).

    Responsibilities:
    - Own the YouTubeChatClient lifecycle (poll loop, shutdown)
    - Enforce YouTube API quota via runtime quota registry
    - Emit normalized chat events for trigger routing
    - Remain cancellation-safe and side-effect free on import
    """

    def __init__(
        self,
        *,
        ctx,
        api_key: str,
        live_chat_id: str,
        poll_interval: Optional[float] = None,
        action_executor: Optional[ActionExecutor] = None,
    ):
        if not api_key:
            raise RuntimeError("YouTube api_key is required")
        if not live_chat_id:
            raise RuntimeError("YouTube live_chat_id is required")

        self.ctx = ctx
        self.live_chat_id = live_chat_id

        # --------------------------------------------------
        # QUOTA REGISTRATION (AUTHORITATIVE)
        # --------------------------------------------------

        limits = ctx.limits or {}

        yt_max = limits.get("youtube_daily_units_max")
        yt_buffer = limits.get("youtube_daily_units_buffer", 0)

        self._quota = None

        if yt_max:
            self._quota = quota_registry.register(
                creator_id=ctx.creator_id,
                platform="youtube",
                max_units=int(yt_max),
                buffer_units=int(yt_buffer),
            )

            log.info(
                f"[{ctx.creator_id}] YouTube quota registered "
                f"(max={yt_max}, buffer={yt_buffer})"
            )
        else:
            log.warning(
                f"[{ctx.creator_id}] No YouTube quota configured — "
                "API usage will NOT be limited"
            )

        # --------------------------------------------------
        # API CLIENT
        # --------------------------------------------------

        self._client = YouTubeChatClient(
            api_key=api_key,
            live_chat_id=live_chat_id,
            creator_id=ctx.creator_id,
            quota_tracker=self._quota,
            poll_interval=poll_interval or 2.5,
        )

        # --------------------------------------------------
        # Trigger registry (per-creator, per-platform)
        # --------------------------------------------------

        self._triggers = TriggerRegistry(creator_id=ctx.creator_id)
        self._triggers.register(NonEmptyChatValidationTrigger())
        self._actions = action_executor

        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker starting")
        backoff = 2.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                runtime_state.record_platform_status(
                    "youtube", "connecting", creator_id=self.ctx.creator_id
                )

                runtime_state.record_platform_status(
                    "youtube", "connected", creator_id=self.ctx.creator_id, success=True
                )

                async for message in self._client.iter_messages():
                    await self._handle_message(message)
                    if self._stop_event.is_set():
                        break

                if self._stop_event.is_set():
                    break

                raise RuntimeError("YouTube chat polling ended unexpectedly")

            except asyncio.CancelledError:
                log.debug(f"[{self.ctx.creator_id}] YouTube chat worker cancelled")
                raise
            except QuotaExceeded as e:
                runtime_state.record_platform_error("youtube", str(e), self.ctx.creator_id)
                log.error(
                    f"[{self.ctx.creator_id}] YouTube quota exceeded — chat polling halted"
                )
                break
            except QuotaBufferWarning as warn:
                log.warning(f"[{self.ctx.creator_id}] YouTube quota buffer warning: {warn}")
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
            except Exception as e:
                runtime_state.record_platform_error("youtube", str(e), self.ctx.creator_id)
                log.warning(f"[{self.ctx.creator_id}] YouTube chat worker error: {e}")
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
        runtime_state.record_platform_status("youtube", "inactive", creator_id=self.ctx.creator_id)
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker stopped")

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: YouTubeChatMessage):
        """
        Routing hook for chat messages.
        """
        event = message.to_event()
        event["creator_id"] = self.ctx.creator_id
        event["channel"] = message.live_chat_id
        event["platform"] = "youtube"

        runtime_state.record_platform_event("youtube", creator_id=self.ctx.creator_id)
        runtime_state.record_platform_heartbeat("youtube")

        log.debug(
            f"[{self.ctx.creator_id}] [YouTube liveChat={message.live_chat_id}] "
            f"{message.author_name}: {message.text}"
        )

        # --------------------------------------------------
        # Trigger evaluation (execution happens elsewhere)
        # --------------------------------------------------

        actions = self._triggers.process(event)
        if actions:
            runtime_state.record_trigger_actions("youtube", len(actions), creator_id=self.ctx.creator_id)
        for action in actions:
            log.debug(
                f"[{self.ctx.creator_id}] Trigger action emitted: {action}"
            )

        if self._actions and actions:
            await self._actions.execute(actions, default_platform="youtube")

        if actions:
            try:
                runtime_snapshot_exporter.publish()
            except Exception:
                log.debug("Runtime snapshot publish skipped for YouTube trigger")
