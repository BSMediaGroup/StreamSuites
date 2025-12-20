from typing import Optional

from services.youtube.api.chat import YouTubeChatClient
from services.youtube.models.message import YouTubeChatMessage
from services.triggers.registry import TriggerRegistry
from shared.logging.logger import get_logger

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

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker starting")

        try:
            async for message in self._client.iter_messages():
                await self._handle_message(message)

        except QuotaExceeded as e:
            log.error(
                f"[{self.ctx.creator_id}] YouTube quota exceeded — "
                "chat polling halted"
            )
            log.error(str(e))

        except QuotaBufferWarning as e:
            # Should not normally bubble this far, but safe to log
            log.warning(
                f"[{self.ctx.creator_id}] YouTube quota buffer warning"
            )
            log.warning(str(e))

        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] YouTube chat worker error: {e}"
            )

        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        await self._client.close()
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker stopped")

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: YouTubeChatMessage):
        """
        Routing hook for chat messages.
        """
        event = message.to_event()

        log.debug(
            f"[{self.ctx.creator_id}] [YouTube liveChat={message.live_chat_id}] "
            f"{message.author_name}: {message.text}"
        )

        # --------------------------------------------------
        # Trigger evaluation (execution happens elsewhere)
        # --------------------------------------------------

        actions = self._triggers.process(event)
        for action in actions:
            log.debug(
                f"[{self.ctx.creator_id}] Trigger action emitted: {action}"
            )
