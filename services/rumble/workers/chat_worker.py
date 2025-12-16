import asyncio
from typing import Optional, Set, Tuple
from datetime import datetime, timezone

from core.jobs import JobRegistry
from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

POLL_SECONDS = 2
SEND_COOLDOWN_SECONDS = 0.75
STARTUP_ANNOUNCEMENT = "🤖 StreamSuites bot online"


class RumbleChatWorker:
    """
    MODEL A — CHAT WORKER (POC-FAITHFUL, HARDENED)

    READ: Livestream API (authoritative)
    SEND: DOM injection (Playwright keyboard)
    """

    def __init__(
        self,
        ctx,
        jobs: JobRegistry,
        watch_url: str,
    ):
        self.ctx = ctx
        self.jobs = jobs
        self.watch_url = watch_url

        self.browser: Optional[RumbleBrowserClient] = None

        # Seen message de-duplication
        self._seen: Set[Tuple[str, str, str]] = set()

        # Concurrency + rate limiting
        self._lock = asyncio.Lock()
        self._last_send_ts: float = 0.0

        # Startup baseline control
        self._startup_sync_complete = False
        self._startup_cutoff_ts: Optional[datetime] = None
        self._startup_announced = False

        self._poll_count = 0

    # ------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        self.browser = RumbleBrowserClient.instance()

        await self.browser.start()
        await self.browser.ensure_logged_in()

        log.info(
            f"[{self.ctx.creator_id}] Navigating to livestream → {self.watch_url}"
        )

        await self.browser.open_watch(self.watch_url)
        await self.browser.wait_for_chat_ready()

    # ------------------------------------------------------------

    async def run(self):
        log.info(
            f"[{self.ctx.creator_id}] Chat worker starting (API READ / DOM SEND)"
        )

        if not self.ctx.rumble_livestream_api_url:
            raise RuntimeError(
                f"[{self.ctx.creator_id}] rumble_livestream_api_url is missing"
            )

        log.info(
            f"[{self.ctx.creator_id}] Livestream API URL resolved → "
            f"{self.ctx.rumble_livestream_api_url}"
        )

        await self._ensure_browser()

        log.info(
            f"[{self.ctx.creator_id}] Chat ready — entering API poll loop"
        )

        while True:
            try:
                await self._poll_api_chat()
                await asyncio.sleep(POLL_SECONDS)

            except asyncio.CancelledError:
                raise

            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Chat poll error: {e}"
                )
                await asyncio.sleep(5)

    # ------------------------------------------------------------

    async def _poll_api_chat(self) -> None:
        if not self.browser or not self.browser._context:
            log.warning(
                f"[{self.ctx.creator_id}] Browser context not ready yet"
            )
            return

        self._poll_count += 1

        response = await self.browser._context.request.get(
            self.ctx.rumble_livestream_api_url,
            timeout=10000,
            headers={"Accept": "application/json"},
        )

        status = response.status
        log.info(
            f"[{self.ctx.creator_id}] API poll #{self._poll_count} → HTTP {status}"
        )

        if status != 200:
            body = await response.text()
            body_preview = body[:500].replace("\n", "\\n")
            raise RuntimeError(
                f"Livestream API HTTP {status} body={body_preview}"
            )

        data = await response.json()

        streams = data.get("livestreams", []) or []
        live_streams = [s for s in streams if s.get("is_live")]

        log.info(
            f"[{self.ctx.creator_id}] API data → livestreams={len(streams)} "
            f"live={len(live_streams)}"
        )

        total_msgs = 0
        newest_ts: Optional[datetime] = None

        for stream in live_streams:
            chat = stream.get("chat", {}) or {}
            recent = chat.get("recent_messages", []) or []

            total_msgs += len(recent)

            for msg in recent:
                created_raw = msg.get("created_on")
                if not created_raw:
                    continue

                try:
                    created_ts = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    )
                except Exception:
                    continue

                if not newest_ts or created_ts > newest_ts:
                    newest_ts = created_ts

                key = (
                    msg.get("username"),
                    msg.get("text"),
                    created_raw,
                )

                if key in self._seen:
                    continue

                self._seen.add(key)

                # --------------------------------------------------
                # 🔒 STARTUP BASELINE SYNC (FIRST POLL ONLY)
                # --------------------------------------------------
                if not self._startup_sync_complete:
                    continue

                user = (msg.get("username") or "").strip()
                text = (msg.get("text") or "").strip()

                if not user or not text:
                    continue

                if self._startup_cutoff_ts and created_ts <= self._startup_cutoff_ts:
                    continue

                log.info(
                    f"💬 {user}: {text} (created_on={created_raw})"
                )

                if text.lower() == "!ping":
                    await self._send_pong(user)

        # --------------------------------------------------
        # FINALIZE STARTUP BASELINE
        # --------------------------------------------------
        if not self._startup_sync_complete:
            self._startup_cutoff_ts = newest_ts
            self._startup_sync_complete = True
            log.info(
                f"[{self.ctx.creator_id}] Startup baseline established "
                f"(cutoff={self._startup_cutoff_ts})"
            )

        # --------------------------------------------------
        # STARTUP ANNOUNCEMENT (ONCE, AFTER BASELINE)
        # --------------------------------------------------
        if self._startup_sync_complete and not self._startup_announced:
            await self._send_startup_announcement()

        log.info(
            f"[{self.ctx.creator_id}] API poll #{self._poll_count} → "
            f"recent_messages_total={total_msgs}"
        )

    # ------------------------------------------------------------

    async def _send_startup_announcement(self):
        async with self._lock:
            if self._startup_announced:
                return

            log.info(
                f"[{self.ctx.creator_id}] Sending startup announcement"
            )

            sent = await self.browser.send_chat_dom(
                STARTUP_ANNOUNCEMENT
            )

            if sent:
                self._startup_announced = True
                self._last_send_ts = asyncio.get_event_loop().time()
                log.info("📣 Startup announcement sent")
            else:
                log.error("❌ Startup announcement failed")

    # ------------------------------------------------------------

    async def _send_pong(self, user: str):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            delta = now - self._last_send_ts

            if delta < SEND_COOLDOWN_SECONDS:
                await asyncio.sleep(SEND_COOLDOWN_SECONDS - delta)

            log.info(
                f"[{self.ctx.creator_id}] !ping detected from {user} — replying pong"
            )

            sent = await self.browser.send_chat_dom("pong")

            if sent:
                self._last_send_ts = asyncio.get_event_loop().time()
                log.info("📤 pong sent")
            else:
                log.error("❌ pong failed")
