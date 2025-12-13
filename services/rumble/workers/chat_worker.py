import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from core.jobs import JobRegistry
from services.rumble.chat_client import RumbleChatClient
from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    """
    WebSocket-driven Rumble chat worker.

    CRITICAL DESIGN:
    - Chat is READ via Playwright WebSocket (browser-owned)
    - Chat is SENT via REST POST (RumbleChatClient)
    - NO REST polling
    - Browser MUST stay open
    """

    def __init__(self, ctx, jobs: JobRegistry, channel_id: str):
        self.ctx = ctx
        self.jobs = jobs
        self.channel_id = str(channel_id)

        self.last_clip_time = 0.0
        self.clip_rules = self._load_clip_rules()

        self.client: Optional[RumbleChatClient] = None
        self._browser: Optional[RumbleBrowserClient] = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"enabled": False}

    async def _ensure_browser_and_client(self):
        """
        Ensure:
        - Persistent browser is running
        - Browser is navigated to the WATCH PAGE
        - Fresh cookies are harvested
        - REST client is ready for sending messages
        """
        self._browser = RumbleBrowserClient.instance()

        # Browser MUST navigate to watch page to attach chat WS
        watch_url = getattr(self.ctx, "rumble_watch_url", None)
        if not watch_url:
            raise RuntimeError("ctx.rumble_watch_url is required but missing")

        await self._browser.start(watch_url=watch_url)

        cookies = await self._browser.get_cookie_dict_for("rumble.com")

        required = ["u_s", "a_s", "cf_clearance"]
        missing = [k for k in required if k not in cookies]

        if missing:
            raise RuntimeError(
                f"Missing required Rumble cookies from browser: {missing}. "
                f"Log into Rumble in the opened browser window."
            )

        self.client = RumbleChatClient(cookies)

        # Subscribe to browser WebSocket chat feed
        self._browser.subscribe_chat(self._on_chat_message)

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    async def run(self):
        log.info(
            f"[{self.ctx.creator_id}] Rumble chat bot active "
            f"(channel={self.channel_id}, websocket mode)"
        )

        try:
            await self._ensure_browser_and_client()

            # Keep task alive forever; browser pushes messages via callback
            while True:
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Chat worker crashed: {e}")

    # ------------------------------------------------------------------
    # WebSocket inbound messages
    # ------------------------------------------------------------------

    def _on_chat_message(self, msg: dict):
        """
        Called directly from Playwright WebSocket listener.
        MUST be sync-safe → offload async work.
        """
        try:
            text = str(msg.get("text", "")).strip()
            user = (msg.get("user") or {}).get("username", "unknown")

            if not text:
                return

            asyncio.create_task(self._handle_message(user, text))

        except Exception:
            return

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    async def _handle_message(self, user: str, text: str):
        if not text.lower().startswith("!clip"):
            return

        now = time.time()
        cooldown = int(self.clip_rules.get("cooldown_seconds", 30))

        if now - self.last_clip_time < cooldown:
            self.client.send_message(
                self.channel_id,
                "⏳ Cooldown active. Try again shortly."
            )
            return

        length = int(self.clip_rules.get("default_length", 30))
        parts = text.split()

        if len(parts) > 1:
            try:
                length = int(parts[1])
            except ValueError:
                self.client.send_message(
                    self.channel_id,
                    "❌ Invalid clip length."
                )
                return

        max_len = int(self.clip_rules.get("max_length", 90))
        if length > max_len:
            self.client.send_message(
                self.channel_id,
                f"❌ Clip too long (max {max_len}s)."
            )
            return

        self.last_clip_time = now

        await self.jobs.dispatch(
            job_type="clip",
            ctx=self.ctx,
            payload={
                "length": length,
                "requested_by": user,
                "platform": "rumble",
            },
        )

        self.client.send_message(
            self.channel_id,
            f"🎬 Clip queued ({length}s)"
        )
