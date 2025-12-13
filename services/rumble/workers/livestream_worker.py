import asyncio
from typing import Optional

from core.jobs import JobRegistry
from services.rumble.workers.chat_worker import RumbleChatWorker
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    """
    Attaches the StreamSuites chat bot to a Rumble chat channel
    using REST (cookie-authenticated).

    IMPORTANT:
      - This worker does NOT detect live/offline state
      - This worker does NOT scrape pages
      - This worker treats rumble_chat_channel_id as authoritative
    """

    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        # REQUIRED config
        self.channel_id: Optional[str] = getattr(
            ctx, "rumble_chat_channel_id", None
        )

        self.chat_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        if not self.channel_id:
            log.error(
                f"[{self.ctx.creator_id}] Missing rumble_chat_channel_id in creator config"
            )
            return

        while True:
            try:
                # Restart chat worker if needed
                if not self.chat_task or self.chat_task.done():
                    if self.chat_task and self.chat_task.done():
                        if not self.chat_task.cancelled():
                            exc = self.chat_task.exception()
                            if exc:
                                log.error(
                                    f"[{self.ctx.creator_id}] Chat worker crashed: {exc}"
                                )

                    await self._start_chat()

            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Livestream worker error: {e}"
                )
                await asyncio.sleep(5)

            await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # Chat lifecycle
    # ------------------------------------------------------------------

    async def _start_chat(self):
        log.info(
            f"[{self.ctx.creator_id}] Attaching bot to Rumble chat channel {self.channel_id}"
        )

        worker = RumbleChatWorker(
            ctx=self.ctx,
            jobs=self.jobs,
            channel_id=str(self.channel_id),
        )

        self.chat_task = asyncio.create_task(worker.run())

    async def _stop_chat(self):
        if self.chat_task:
            log.info(
                f"[{self.ctx.creator_id}] Detaching bot from Rumble chat"
            )
            self.chat_task.cancel()
            try:
                await self.chat_task
            except Exception:
                pass
            self.chat_task = None
