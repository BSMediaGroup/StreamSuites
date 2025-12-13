import asyncio
from typing import Optional

from services.rumble.api.channel_page import fetch_channel_livestream_state
from services.rumble.api.watch_page import fetch_watch_page_chat_state
from services.rumble.workers.chat_worker import RumbleChatWorker
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        # Existing channel-based config (retained)
        self.channel_url = getattr(ctx, "rumble_channel_url", None)

        # NEW: direct watch-page override (optional but preferred)
        self.watch_url = getattr(ctx, "rumble_watch_url", None)

        self.chat_task: Optional[asyncio.Task] = None
        self.current_room_id: Optional[str] = None
        self.chat_post_path: Optional[str] = None

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        if not self.channel_url and not self.watch_url:
            log.error(
                f"[{self.ctx.creator_id}] Missing rumble_channel_url or rumble_watch_url in creator config"
            )
            return

        while True:
            try:
                # Prefer watch-page detection if provided
                if self.watch_url:
                    await self._check_watch_page()
                else:
                    await self._check_channel()
            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Livestream worker error: {e}"
                )

            await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # EXISTING CHANNEL-BASED FLOW (RETAINED)
    # ------------------------------------------------------------------

    async def _check_channel(self):
        state = await fetch_channel_livestream_state(
            channel_url=self.channel_url
        )

        livestream = self._extract_livestream(state)
        if not livestream:
            await self._stop_chat()
            return

        room_id = livestream.get("chatRoomId")
        post_path = livestream.get("chatPostPath")

        if not room_id or not post_path:
            log.error(
                f"[{self.ctx.creator_id}] Livestream detected but chat data missing"
            )
            return

        if self.chat_task and self.current_room_id == room_id:
            return

        await self._start_chat(room_id, post_path)

    def _extract_livestream(self, state: dict) -> Optional[dict]:
        """
        Walk the initial state tree to locate live stream data.
        Legacy channel-page method (kept for backward compatibility).
        """
        try:
            if not isinstance(state, dict):
                return None

            channel = state.get("channel", {})
            if not isinstance(channel, dict):
                return None

            livestreams = channel.get("livestreams", [])
            if not isinstance(livestreams, list):
                return None

            for item in livestreams:
                if item.get("isLive"):
                    chat = item.get("chat", {}) or {}
                    return {
                        "chatRoomId": chat.get("roomId"),
                        "chatPostPath": chat.get("postPath"),
                    }
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # NEW WATCH-PAGE FLOW (AUTHORITATIVE)
    # ------------------------------------------------------------------

    async def _check_watch_page(self):
        state = await fetch_watch_page_chat_state(self.watch_url)

        if not state.get("is_live"):
            await self._stop_chat()
            return

        room_id = state.get("chat_room_id")
        post_path = state.get("chat_post_path")

        if not room_id or not post_path:
            log.error(
                f"[{self.ctx.creator_id}] Watch page live but chat data missing"
            )
            return

        if self.chat_task and self.current_room_id == room_id:
            return

        await self._start_chat(room_id, post_path)

    # ------------------------------------------------------------------
    # CHAT LIFECYCLE (UNCHANGED)
    # ------------------------------------------------------------------

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
