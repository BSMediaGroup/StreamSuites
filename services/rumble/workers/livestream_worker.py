import asyncio
import os
from typing import Optional

from services.rumble.api.channel_page import fetch_channel_livestream_state
from services.rumble.workers.chat_worker import RumbleChatWorker
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        self.channel_url = ctx.rumble_channel_url
        self.cookie = os.getenv(
            f"RUMBLE_BOT_SESSION_COOKIE_{ctx.creator_id.upper()}"
        )

        self.chat_task: Optional[asyncio.Task] = None
        self.current_room_id: Optional[str] = None
        self.chat_post_path: Optional[str] = None

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        while True:
            try:
                await self._check_channel()
            except Exception as e:
                log.error(f"Livestream worker error: {e}")

            await asyncio.sleep(10)

    async def _check_channel(self):
        state = await fetch_channel_livestream_state(
            channel_url=self.channel_url,
            cookie=self.cookie
        )

        livestream = self._extract_livestream(state)
        if not livestream:
            await self._stop_chat()
            return

        room_id = livestream.get("chatRoomId")
        post_path = livestream.get("chatPostPath")

        if not room_id or not post_path:
            log.error("Livestream detected but chat data missing")
            return

        if self.chat_task and self.current_room_id == room_id:
            return

        await self._start_chat(room_id, post_path)

    def _extract_livestream(self, state: dict) -> Optional[dict]:
        """
        Walk the initial state tree to locate live stream data.
        """
        try:
            for item in state.get("channel", {}).get("livestreams", []):
                if item.get("isLive"):
                    return {
                        "chatRoomId": item.get("chat", {}).get("roomId"),
                        "chatPostPath": item.get("chat", {}).get("postPath")
                    }
        except Exception:
            pass

        return None

    async def _start_chat(self, room_id: str, post_path: str):
        await self._stop_chat()

        log.info(
            f"[{self.ctx.creator_id}] Live detected — starting chat bot"
        )

        worker = RumbleChatWorker(
            ctx=self.ctx,
            jobs=self.jobs,
            room_id=room_id,
            post_path=post_path
        )

        self.current_room_id = room_id
        self.chat_post_path = post_path
        self.chat_task = asyncio.create_task(worker.run())

    async def _stop_chat(self):
        if self.chat_task:
            log.info(
                f"[{self.ctx.creator_id}] Stream offline — stopping chat bot"
            )
            self.chat_task.cancel()
            self.chat_task = None
            self.current_room_id = None
            self.chat_post_path = None
