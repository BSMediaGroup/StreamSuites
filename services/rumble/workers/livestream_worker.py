import asyncio
from typing import Optional

from services.rumble.workers.chat_worker import RumbleChatWorker
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    """
    Attaches the StreamSuites chat bot to a Rumble livestream chat
    using the REST chat API (cookie-authenticated).

    This worker NO LONGER:
    - scrapes watch pages
    - inspects DOM / iframes
    - listens to WebSockets
    - discovers room IDs dynamically

    The livestream chat channel ID is treated as authoritative.
    """

    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        # REQUIRED: known livestream chat channel ID
        # Example: 424574510
        self.channel_id: Optional[str] = getattr(
            ctx, "rumble_chat_channel_id", None
        )

        self.chat_task: Optional[asyncio.Task] = None

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        if not self.channel_id:
            log.error(
                f"[{self.ctx.creator_id}] Missing rumble_chat_channel_id in creator config"
            )
            return

        while True:
            try:
                if not self.chat_task:
                    await self._start_chat()
            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Livestream worker error: {e}"
                )

            # This loop no longer polls for live/offline
            # Chat availability is enforced server-side by Rumble
            await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # CHAT LIFECYCLE
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
            self.chat_task = None
