"""
Discord Status Module

Responsibilities:
- Manage custom Discord bot presence (text + emoji)
- Persist status in shared state (JSON-backed)
- Provide async-safe update hooks for supervisor / commands
- Emit structured logs for dashboard + diagnostics

IMPORTANT:
- This module does NOT register commands
- This module does NOT own the Discord client
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import discord

from shared.logging.logger import get_logger
from shared.storage.paths import get_state_path

log = get_logger("discord.status")


STATUS_STATE_FILE = "discord_status.json"


class DiscordStatusManager:
    def __init__(self):
        self._status_text: Optional[str] = None
        self._status_emoji: Optional[str] = None

        # --------------------------------------------------
        # FIX: get_state_path now requires a name argument
        # --------------------------------------------------
        self._state_path = get_state_path(f"discord/{STATUS_STATE_FILE}")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_state()

    # --------------------------------------------------

    def _load_state(self):
        if not self._state_path.exists():
            log.info("No existing Discord status state found")
            return

        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            self._status_text = data.get("text")
            self._status_emoji = data.get("emoji")
            log.info(
                f"Loaded Discord status: text={self._status_text!r} "
                f"emoji={self._status_emoji!r}"
            )
        except Exception as e:
            log.warning(f"Failed to load Discord status state: {e}")

    def _save_state(self):
        try:
            payload = {
                "text": self._status_text,
                "emoji": self._status_emoji,
            }
            self._state_path.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error(f"Failed to save Discord status state: {e}")

    # --------------------------------------------------

    async def apply(self, bot: discord.Client):
        """
        Apply the current status to the Discord client.
        Safe to call multiple times.
        """
        if not self._status_text:
            log.debug("No Discord status text set — skipping presence update")
            return

        activity = discord.CustomActivity(
            name=self._status_text,
            emoji=self._status_emoji,
        )

        try:
            await bot.change_presence(activity=activity)
            log.info(
                f"Discord presence updated: "
                f"text={self._status_text!r} "
                f"emoji={self._status_emoji!r}"
            )
        except Exception as e:
            log.error(f"Failed to apply Discord status: {e}")

    # --------------------------------------------------

    async def set_status(
        self,
        *,
        text: str,
        emoji: Optional[str] = None,
        bot: Optional[discord.Client] = None,
    ):
        """
        Update and persist the Discord status.
        Optionally applies immediately if bot is provided.
        """
        self._status_text = text
        self._status_emoji = emoji
        self._save_state()

        log.info(
            f"Discord status set: text={text!r} emoji={emoji!r}"
        )

        if bot:
            await self.apply(bot)

    # --------------------------------------------------

    def snapshot(self) -> dict:
        """
        Return current status for dashboard / diagnostics.
        """
        return {
            "text": self._status_text,
            "emoji": self._status_emoji,
        }
