import asyncio
import os
from typing import Optional

from services.rumble.api.livestream import fetch_livestream_data
from services.rumble.workers.chat_worker import RumbleChatWorker
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        self.api_key = os.getenv(
            f"RUMBLE_LIVESTREAM_KEY_{ctx.creator_id.upper()}"
        )

        self.chat_task: Optional[asyncio.Task] = None
        self.current_room_id: Optional[str] = None
        self.chat_post_path: Optional[str] = None

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        while True:
            await self._check_livestream()
            await asyncio.sleep(15)

    async def _check_livestream(self):
        if not self.api_key:
            log.error(f"[{self.ctx.creator_id}] Missing RUMBLE_LIVESTREAM_KEY")
            return

        data = await fetch_livestream_data(self.api_key)
        livestream = data.get("livestream", {})

        is_live = bool(livestream.get("is_live"))
        chat = livestream.get("chat", {}) or {}

        room_id = chat.get("room_id")
        post_path = chat.get("post_path")

        if is_live and room_id and post_path:
            if (
                self.chat_task
                and self.current_room_id == room_id
            ):
                return

            await self._start_chat(room_id, post_path)
        else:
            await self._stop_chat()

    async def _start_chat(self, room_id: str, post_path: str):
        await self._stop_chat()

        log.info(
            f"[{self.ctx.creator_id}] Stream live, starting chat bot"
        )

        chat_worker = RumbleChatWorker(
            ctx=self.ctx,
            jobs=self.jobs,
            room_id=room_id,
            post_path=post_path
        )

        self.current_room_id = room_id
        self.chat_post_path = post_path
        self.chat_task = asyncio.create_task(chat_worker.run())

    async def _stop_chat(self):
        if self.chat_task:
            log.info(
                f"[{self.ctx.creator_id}] Stream offline, stopping chat bot"
            )
            self.chat_task.cancel()
            self.chat_task = None
            self.current_room_id = None
            self.chat_post_path = None
