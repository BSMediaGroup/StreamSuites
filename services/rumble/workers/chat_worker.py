import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from core.jobs import JobRegistry
from services.rumble.api.chat import fetch_chat_messages
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    def __init__(
        self,
        ctx,
        jobs: JobRegistry,
        room_id: str
    ):
        self.ctx = ctx
        self.jobs = jobs
        self.room_id = room_id

        self.last_seen_timestamp: int = 0
        self.last_clip_time: float = 0.0

        self.clip_rules = self._load_clip_rules()

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {
                "enabled": False
            }

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble chat worker started")

        while True:
            await self._poll()
            await asyncio.sleep(2)

    async def _poll(self):
        messages = await fetch_chat_messages(
            room_id=self.room_id,
            since=self.last_seen_timestamp
        )

        for msg in messages:
            timestamp = int(msg.get("time", 0))
            if timestamp <= self.last_seen_timestamp:
                continue

            self.last_seen_timestamp = timestamp

            text = str(msg.get("text", "")).strip()
            user = msg.get("user", "unknown")

            await self._handle_message(user, text)

    async def _handle_message(self, user: str, text: str):
        if not text.lower().startswith("!clip"):
            return

        if not self.clip_rules.get("enabled", False):
            log.info("Clipping disabled by rules")
            return

        now = time.time()
        cooldown = self.clip_rules.get("cooldown_seconds", 30)

        if now - self.last_clip_time < cooldown:
            log.info("Clip command ignored due to cooldown")
            return

        parts = text.split()
        length = self.clip_rules.get("default_length", 30)

        if len(parts) >= 2:
            try:
                length = int(parts[1])
            except ValueError:
                return

        min_len = self.clip_rules.get("min_length", 5)
        max_len = self.clip_rules.get("max_length", 90)

        if length < min_len or length > max_len:
            log.info(f"Invalid clip length requested: {length}")
            return

        self.last_clip_time = now

        log.info(
            f"[{self.ctx.creator_id}] Clip requested by {user} ({length}s)"
        )

        await self.jobs.dispatch(
            job_type="clip",
            ctx=self.ctx,
            payload={
                "length": length,
                "requested_by": user,
                "platform": "rumble"
            }
        )
