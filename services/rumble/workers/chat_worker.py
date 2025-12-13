import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional

from core.jobs import JobRegistry
from services.rumble.chat_client import RumbleChatClient
from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    """
    Stateful chat worker for a single Rumble chat channel.

    IMPORTANT:
    - Cookies are sourced LIVE from the persistent Playwright browser
    - NO cookies are read from .env anymore
    - This keeps cf_clearance / __cf_bm / session cookies fresh automatically
    """

    def __init__(self, ctx, jobs: JobRegistry, channel_id: str):
        self.ctx = ctx
        self.jobs = jobs
        self.channel_id = str(channel_id)

        self.last_seen_id: Optional[str] = None
        self.last_clip_time = 0.0

        self.clip_rules = self._load_clip_rules()

        self.client: Optional[RumbleChatClient] = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"enabled": False}

    async def _ensure_client(self) -> None:
        """
        Ensure we have a chat client with FRESH cookies from the browser.
        This can be re-run safely if cookies rotate.
        """
        browser = RumbleBrowserClient.instance()

        # Ensure browser is running & logged in
        await browser.start()

        cookies: Dict[str, str] = await browser.get_cookie_dict_for("rumble.com")

        # Hard requirement: these MUST exist or chat will fail
        required = ["u_s", "a_s", "cf_clearance"]
        missing = [k for k in required if k not in cookies]

        if missing:
            raise RuntimeError(
                f"Missing required Rumble cookies from browser: {missing}. "
                f"Open the browser window and log into Rumble manually."
            )

        self.client = RumbleChatClient(cookies)

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    async def run(self):
        log.info(
            f"[{self.ctx.creator_id}] Rumble chat bot active "
            f"(channel={self.channel_id})"
        )

        try:
            # Initial client bootstrap
            await self._ensure_client()

            while True:
                try:
                    await self._poll()
                except Exception as e:
                    # Any fetch/send failure → refresh cookies + client
                    log.error(
                        f"[{self.ctx.creator_id}] Chat poll error, refreshing cookies: {e}"
                    )
                    await self._ensure_client()

                await asyncio.sleep(2)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Chat worker crashed: {e}")

    async def _poll(self):
        if not self.client:
            return

        messages = self.client.fetch_messages(
            channel_id=self.channel_id,
            since_id=self.last_seen_id,
        )

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            # Advance cursor
            self.last_seen_id = str(msg_id)

            text = str(msg.get("text", "")).strip()
            user = (msg.get("user") or {}).get("username", "unknown")

            if text:
                await self._handle_message(user, text)

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
                self.channel_id, "⏳ Cooldown active. Try again shortly."
            )
            return

        length = int(self.clip_rules.get("default_length", 30))
        parts = text.split()

        if len(parts) > 1:
            try:
                length = int(parts[1])
            except ValueError:
                self.client.send_message(
                    self.channel_id, "❌ Invalid clip length."
                )
                return

        max_len = int(self.clip_rules.get("max_length", 90))
        if length > max_len:
            self.client.send_message(
                self.channel_id, f"❌ Clip too long (max {max_len}s)."
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
            self.channel_id, f"🎬 Clip queued ({length}s)"
        )
