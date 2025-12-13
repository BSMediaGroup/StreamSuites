import asyncio
from typing import Optional

from services.rumble.api.channel_page import fetch_channel_livestream_state
from services.rumble.api.watch_page import fetch_watch_page_chat_state
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.rumble.workers.chat_worker import RumbleChatWorker
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    """
    Monitors a creator's Rumble presence and attaches a chat bot
    to the PRIORITY-LATEST livestream only.
    """

    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        # Backward-compatible config
        self.channel_url = getattr(ctx, "rumble_channel_url", None)

        # Authoritative: watch-page URL (recommended)
        self.watch_url = getattr(ctx, "rumble_watch_url", None)

        # Chat runtime state
        self.chat_task: Optional[asyncio.Task] = None
        self.current_room_id: Optional[str] = None
        self.chat_post_path: Optional[str] = None

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble livestream worker started")

        if not self.watch_url and not self.channel_url:
            log.error(
                f"[{self.ctx.creator_id}] Missing rumble_watch_url or rumble_channel_url in creator config"
            )
            return

        # Ensure browser is running early
        await RumbleBrowserClient.instance().start()

        while True:
            try:
                # Prefer watch-page flow (authoritative)
                if self.watch_url:
                    await self._check_watch_page_priority_latest()
                else:
                    await self._check_channel_legacy()
            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Livestream worker error: {e}"
                )

            await asyncio.sleep(8)

    # ------------------------------------------------------------------
    # AUTHORITATIVE FLOW — WATCH PAGE + PRIORITY-LATEST
    # ------------------------------------------------------------------

    async def _check_watch_page_priority_latest(self):
        """
        Navigate the watch page to allow browser interception,
        then attach to the MOST RECENT livestream only.
        """
        # Trigger navigation & interception
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

        # Already attached to this stream
        if self.chat_task and self.current_room_id == room_id:
            return

        # Newer livestream detected → switch
        await self._start_chat(room_id, post_path)

    # ------------------------------------------------------------------
    # LEGACY FLOW — CHANNEL PAGE (KEPT FOR FALLBACK)
    # ------------------------------------------------------------------

    async def _check_channel_legacy(self):
        """
        Legacy channel-page method.
        Retained for backward compatibility only.
        """
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
        Walk the channel state tree to locate live stream data.
        """
        try:
            if not isinstance(state, dict):
                return None

            channel = state.get("channel", {})
            livestreams = channel.get("livestreams", [])

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
    # CHAT LIFECYCLE
    # ------------------------------------------------------------------

    async def _start_chat(self, room_id: str, post_path: str):
        await self._stop_chat()

        log.info(
            f"[{self.ctx.creator_id}] Attaching bot to livestream chat (room={room_id})"
        )

        worker = RumbleChatWorker(
            ctx=self.ctx,
            jobs=self.jobs,
            room_id=room_id,
            post_path=post_path,
            announce=True,  # announce on attach (locked decision)
        )

        self.current_room_id = room_id
        self.chat_post_path = post_path
        self.chat_task = asyncio.create_task(worker.run())

    async def _stop_chat(self):
        if self.chat_task:
            log.info(
                f"[{self.ctx.creator_id}] Detaching bot from livestream chat"
            )
            self.chat_task.cancel()
            self.chat_task = None
            self.current_room_id = None
            self.chat_post_path = None
