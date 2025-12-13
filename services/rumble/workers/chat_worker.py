import asyncio
import json
import os
import time
from pathlib import Path

from core.jobs import JobRegistry
from services.rumble.api.chat import fetch_chat_messages
from services.rumble.api.chat_post import post_chat_message
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    def __init__(self, ctx, jobs: JobRegistry, room_id: str, post_path: str):
        self.ctx = ctx
        self.jobs = jobs
        self.room_id = room_id
        self.post_path = post_path

        self.last_seen_timestamp = 0
        self.last_clip_time = 0.0

        self.clip_rules = self._load_clip_rules()
        self.cookie = os.getenv(
            f"RUMBLE_BOT_SESSION_COOKIE_{ctx.creator_id.upper()}"
        )

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
        messages = await fetch_chat_messages(
            room_id=self.room_id,
            since=self.last_seen_timestamp
        )

        for msg in messages:
            ts = int(msg.get("time", 0))
            if ts <= self.last_seen_timestamp:
                continue

            self.last_seen_timestamp = ts
            text = str(msg.get("text", "")).strip()
            user = msg.get("user", "unknown")

            await self._handle_message(user, text)

    async def _handle_message(self, user: str, text: str):
        if not text.lower().startswith("!clip"):
            return

        now = time.time()
        cooldown = self.clip_rules.get("cooldown_seconds", 30)

        if now - self.last_clip_time < cooldown:
            await self._reply(f"⏳ Cooldown active. Try again shortly.")
            return

        length = self.clip_rules.get("default_length", 30)
        parts = text.split()

        if len(parts) > 1:
            try:
                length = int(parts[1])
            except ValueError:
                await self._reply("❌ Invalid clip length.")
                return

        if length > self.clip_rules.get("max_length", 90):
            await self._reply("❌ Clip too long (max 90s).")
            return

        self.last_clip_time = now

        await self.jobs.dispatch(
            job_type="clip",
            ctx=self.ctx,
            payload={
                "length": length,
                "requested_by": user,
                "platform": "rumble"
            }
        )

        await self._reply(f"🎬 Clip queued ({length}s)")

    async def _reply(self, message: str):
        if not self.cookie:
            log.error("Missing RUMBLE_BOT_SESSION_COOKIE")
            return

        await post_chat_message(
            cookie=self.cookie,
            post_path=self.post_path,
            message=message
        )
