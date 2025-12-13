import asyncio
import json
import os
import time
from pathlib import Path

from core.jobs import JobRegistry
from services.rumble.chat_client import RumbleChatClient
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    def __init__(self, ctx, jobs: JobRegistry, channel_id: str):
        self.ctx = ctx
        self.jobs = jobs
        self.channel_id = channel_id

        self.last_seen_id = None
        self.last_clip_time = 0.0

        self.clip_rules = self._load_clip_rules()

        # Cookies come from env (exported once from Playwright)
        self.cookies = {
            "u_s": os.getenv("RUMBLE_U_S"),
            "a_s": os.getenv("RUMBLE_A_S"),
            "cf_clearance": os.getenv("RUMBLE_CF_CLEARANCE"),
            "__cf_bm": os.getenv("RUMBLE_CF_BM"),
        }

        if not all(self.cookies.values()):
            raise RuntimeError("Missing Rumble auth cookies")

        self.client = RumbleChatClient(self.cookies)

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text())
        except Exception:
            return {"enabled": False}

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble chat bot active")

        while True:
            await self._poll()
            await asyncio.sleep(2)

    async def _poll(self):
        messages = self.client.fetch_messages(
            channel_id=self.channel_id,
            since_id=self.last_seen_id,
        )

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id:
                continue

            self.last_seen_id = msg_id

            text = str(msg.get("text", "")).strip()
            user = msg.get("user", {}).get("username", "unknown")

            await self._handle_message(user, text)

    async def _handle_message(self, user: str, text: str):
        if not text.lower().startswith("!clip"):
            return

        now = time.time()
        cooldown = self.clip_rules.get("cooldown_seconds", 30)

        if now - self.last_clip_time < cooldown:
            self.client.send_message(
                self.channel_id, "⏳ Cooldown active. Try again shortly."
            )
            return

        length = self.clip_rules.get("default_length", 30)
        parts = text.split()

        if len(parts) > 1:
            try:
                length = int(parts[1])
            except ValueError:
                self.client.send_message(
                    self.channel_id, "❌ Invalid clip length."
                )
                return

        if length > self.clip_rules.get("max_length", 90):
            self.client.send_message(
                self.channel_id, "❌ Clip too long (max 90s)."
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
