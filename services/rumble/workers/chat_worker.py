import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

from core.jobs import JobRegistry
from services.rumble.api.chat import fetch_chat_messages
from services.rumble.api.chat_post import post_chat_message
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


class RumbleChatWorker:
    def __init__(
        self,
        ctx,
        jobs: JobRegistry,
        room_id: str,
        post_path: str,
        announce: bool = False,
    ):
        self.ctx = ctx
        self.jobs = jobs
        self.room_id = room_id
        self.post_path = post_path
        self.announce = announce

        self.last_seen_timestamp = 0
        self.last_clip_time = 0.0

        self.clip_rules = self._load_clip_rules()
        self.cookie = os.getenv(
            f"RUMBLE_BOT_SESSION_COOKIE_{ctx.creator_id.upper()}"
        )

        self._did_announce = False

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"enabled": False}

    async def run(self):
        log.info(
            f"[{self.ctx.creator_id}] Rumble chat bot active (room={self.room_id})"
        )

        # Announce once on attach (locked decision)
        if self.announce and not self._did_announce:
            await self._announce_once()

        try:
            while True:
                await self._poll()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            # Expected during handover / shutdown
            log.info(
                f"[{self.ctx.creator_id}] Rumble chat bot cancelled (room={self.room_id})"
            )
            raise
        except Exception as e:
            # Do not crash the whole runtime; log and stop this worker
            log.error(
                f"[{self.ctx.creator_id}] Rumble chat bot fatal error: {e}"
            )

    async def _announce_once(self):
        self._did_announce = True

        # If we cannot post, don’t spam errors; just log once.
        if not self.cookie:
            log.error(
                f"[{self.ctx.creator_id}] Missing RUMBLE_BOT_SESSION_COOKIE — cannot announce"
            )
            return

        display = getattr(self.ctx, "display_name", self.ctx.creator_id)
        # Keep this short and non-annoying (you can change copy later)
        msg = "🤖 StreamSuites bot online — type !clip <seconds> (max 90)."

        try:
            await self._reply(msg)
            log.info(f"[{self.ctx.creator_id}] Announced bot presence in chat")
        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] Failed to announce in chat: {e}"
            )

    async def _poll(self):
        try:
            messages = await fetch_chat_messages(
                room_id=self.room_id,
                since=self.last_seen_timestamp
            )
        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] Chat poll failed: {e}"
            )
            return

        if not messages:
            return

        for msg in messages:
            ts = int(msg.get("time", 0))
            if ts <= self.last_seen_timestamp:
                continue

            self.last_seen_timestamp = ts
            text = str(msg.get("text", "")).strip()
            user = msg.get("user", "unknown")

            try:
                await self._handle_message(user, text)
            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Message handler error: {e}"
                )

    async def _handle_message(self, user: str, text: str):
        # Safety: ignore empty text
        if not text:
            return

        # Only handle clip command for now
        if not text.lower().startswith("!clip"):
            return

        # If clipping is disabled in rules, refuse politely
        if not bool(self.clip_rules.get("enabled", False)):
            await self._reply("❌ Clipping is currently disabled.")
            return

        now = time.time()
        cooldown = int(self.clip_rules.get("cooldown_seconds", 30))

        if now - self.last_clip_time < cooldown:
            await self._reply("⏳ Cooldown active. Try again shortly.")
            return

        length = int(self.clip_rules.get("default_length", 30))
        parts = text.split()

        if len(parts) > 1:
            try:
                length = int(parts[1])
            except ValueError:
                await self._reply("❌ Invalid clip length.")
                return

        max_len = int(self.clip_rules.get("max_length", 90))
        if length > max_len:
            await self._reply(f"❌ Clip too long (max {max_len}s).")
            return

        if length <= 0:
            await self._reply("❌ Clip length must be > 0.")
            return

        self.last_clip_time = now

        # Dispatch the clip job
        await self.jobs.dispatch(
            job_type="clip",
            ctx=self.ctx,
            payload={
                "length": length,
                "requested_by": user,
                "platform": "rumble",
                "room_id": self.room_id,
            }
        )

        await self._reply(f"🎬 Clip queued ({length}s)")

    async def _reply(self, message: str):
        if not self.cookie:
            log.error(
                f"[{self.ctx.creator_id}] Missing RUMBLE_BOT_SESSION_COOKIE"
            )
            return

        try:
            await post_chat_message(
                cookie=self.cookie,
                post_path=self.post_path,
                message=message
            )
        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] Failed to post chat message: {e}"
            )
