
from typing import Optional

from services.youtube.api.chat import YouTubeChatClient
from services.youtube.models.message import YouTubeChatMessage
from shared.logging.logger import get_logger

log = get_logger("youtube.chat_worker", runtime="streamsuites")


class YouTubeChatWorker:
    """
    Scheduler-owned YouTube chat worker (polling).

    Responsibilities:
    - Own the YouTubeChatClient lifecycle (poll loop, shutdown)
    - Emit normalized chat events for future trigger routing
    - Remain cancellation-safe and free of side effects on import
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
        self._client = YouTubeChatClient(
            api_key=api_key,
            live_chat_id=live_chat_id,
            poll_interval=poll_interval or 2.5,
        )

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker starting")
        try:
            async for message in self._client.iter_messages():
                await self._handle_message(message)
        except NotImplementedError as e:
            log.info(f"[{self.ctx.creator_id}] {e}")
        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] YouTube chat worker error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        await self._client.close()
        log.info(f"[{self.ctx.creator_id}] YouTube chat worker stopped")

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: YouTubeChatMessage):
        """
        Placeholder routing hook for chat messages.
        """
        log.debug(
            f"[{self.ctx.creator_id}] [YouTube liveChat={message.live_chat_id}] "
            f"{message.author_name}: {message.text}"
        )
        # TODO: integrate with trigger registry when available
