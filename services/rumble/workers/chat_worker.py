import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

from core.jobs import JobRegistry
from services.rumble.chat_client import RumbleChatClient
from shared.logging.logger import get_logger

log = get_logger("rumble.chat_worker")

CLIP_RULES_FILE = Path("shared/config/clip_rules.json")


def _parse_cookie_header(cookie_header: str) -> Dict[str, str]:
    """
    Convert a Cookie header string like:
      "u_s=...; a_s=...; cf_clearance=...; __cf_bm=..."
    into {"u_s": "...", "a_s": "...", ...}

    This is tolerant of whitespace and missing segments.
    """
    out: Dict[str, str] = {}
    if not cookie_header:
        return out

    parts = [p.strip() for p in cookie_header.split(";") if p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            out[k] = v
    return out


def _cookie_env_key_for_creator(ctx) -> str:
    # Creator IDs in your configs are lowercase like "daniel"
    # Your env uses suffixes like _DANIEL
    cid = getattr(ctx, "creator_id", "") or ""
    return f"RUMBLE_BOT_SESSION_COOKIE_{cid.upper()}"


class RumbleChatWorker:
    def __init__(self, ctx, jobs: JobRegistry, channel_id: str):
        self.ctx = ctx
        self.jobs = jobs
        self.channel_id = str(channel_id)

        self.last_seen_id: Optional[str] = None
        self.last_clip_time = 0.0

        self.clip_rules = self._load_clip_rules()

        # --- Cookie sourcing ---
        # Preferred: full cookie header string, per creator
        cookie_header_key = _cookie_env_key_for_creator(ctx)
        cookie_header = (os.getenv(cookie_header_key) or "").strip()

        cookies = _parse_cookie_header(cookie_header)

        # Fallback: individual cookie vars (global)
        # (This supports your older layout)
        cookies.setdefault("u_s", os.getenv("RUMBLE_U_S") or "")
        cookies.setdefault("a_s", os.getenv("RUMBLE_A_S") or "")
        cookies.setdefault("cf_clearance", os.getenv("RUMBLE_CF_CLEARANCE") or "")
        cookies.setdefault("__cf_bm", os.getenv("RUMBLE_CF_BM") or "")

        # Remove empties
        self.cookies: Dict[str, str] = {k: v for k, v in cookies.items() if v}

        # We require at least the session cookies + CF clearance typically.
        # Don’t hard-crash the whole runtime; log loudly and let worker exit.
        required = ["u_s", "a_s", "cf_clearance"]
        missing = [k for k in required if k not in self.cookies]
        if missing:
            raise RuntimeError(
                f"Missing Rumble auth cookies: {missing}. "
                f"Provide {cookie_header_key} as a full cookie string OR set "
                f"RUMBLE_U_S / RUMBLE_A_S / RUMBLE_CF_CLEARANCE."
            )

        self.client = RumbleChatClient(self.cookies)

    def _load_clip_rules(self) -> dict:
        try:
            return json.loads(CLIP_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"enabled": False}

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Rumble chat bot active (channel={self.channel_id})")

        try:
            while True:
                await self._poll()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            # clean detach
            raise
        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Chat worker crashed: {e}")
            # Don’t re-raise: let livestream_worker recreate it if needed.

    async def _poll(self):
        messages = self.client.fetch_messages(
            channel_id=self.channel_id,
            since_id=self.last_seen_id,
        )

        # If endpoint resolved but returns empty, fine.
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

    async def _handle_message(self, user: str, text: str):
        # Only react to commands (keep it tight)
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
                self.client.send_message(self.channel_id, "❌ Invalid clip length.")
                return

        max_len = int(self.clip_rules.get("max_length", 90))
        if length > max_len:
            self.client.send_message(self.channel_id, f"❌ Clip too long (max {max_len}s).")
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

        self.client.send_message(self.channel_id, f"🎬 Clip queued ({length}s)")
