"""
Discord Client (Control-Plane Runtime)

This module owns the Discord connection itself.
It is intentionally minimal and lifecycle-focused.

Responsibilities:
- connect to Discord
- handle ready / resume / disconnect events
- expose a clean async run() / shutdown() contract
- emit structured logs for supervisor + dashboard use

IMPORTANT:
- This client MUST be controlled by DiscordSupervisor
- This client MUST NOT create its own event loop
- This client MUST NOT start streaming workers
"""

import os
import asyncio
from typing import Optional

import discord
from discord.ext import commands

from dotenv import load_dotenv
from shared.logging.logger import get_logger
from services.discord.status import DiscordStatusManager

# NOTE: routed to Discord runtime log file
log = get_logger("discord.client", runtime="discord")


class DiscordClient:
    """
    Thin wrapper around discord.py Bot.

    This class provides:
    - async run() entrypoint
    - async shutdown()
    - lifecycle event logging
    """

    def __init__(self):
        load_dotenv()

        token = os.getenv("DISCORD_BOT_TOKEN_DANIEL")
        if not token:
            raise RuntimeError(
                "DISCORD_BOT_TOKEN_DANIEL not found in environment"
            )

        self._token: str = token
        self._bot: Optional[commands.Bot] = None
        self._ready_event = asyncio.Event()

        # Status manager (persisted presence)
        self._status = DiscordStatusManager()

    # --------------------------------------------------

    def _build_bot(self) -> commands.Bot:
        """
        Construct the discord.py Bot instance.

        NOTE:
        - Commands and extensions are loaded later
        - This is connection + lifecycle only
        """

        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = False
        intents.messages = True
        intents.message_content = False  # slash-command focused

        bot = commands.Bot(
            command_prefix="!",
            intents=intents,
        )

        # --------------------------------------------------
        # Lifecycle Events
        # --------------------------------------------------

        @bot.event
        async def on_ready():
            log.info(
                f"Discord connected as {bot.user} "
                f"(id={bot.user.id}) "
                f"guilds={len(bot.guilds)}"
            )

            # Apply persisted custom status (if any)
            try:
                await self._status.apply(bot)
            except Exception as e:
                log.warning(f"Failed to apply Discord status on ready: {e}")

            self._ready_event.set()

        @bot.event
        async def on_resumed():
            log.info("Discord connection resumed")

            # Re-apply presence on resume (Discord clears it sometimes)
            try:
                await self._status.apply(bot)
            except Exception as e:
                log.warning(f"Failed to re-apply Discord status on resume: {e}")

        @bot.event
        async def on_disconnect():
            log.warning("Discord connection lost")

        @bot.event
        async def on_guild_join(guild: discord.Guild):
            log.info(
                f"Joined guild: {guild.name} "
                f"(id={guild.id}, members={guild.member_count})"
            )

        @bot.event
        async def on_guild_remove(guild: discord.Guild):
            log.info(
                f"Removed from guild: {guild.name} "
                f"(id={guild.id})"
            )

        return bot

    # --------------------------------------------------

    async def run(self):
        """
        Start the Discord client and block until shutdown.
        """
        if self._bot is not None:
            raise RuntimeError("Discord client already running")

        log.info("Initializing Discord client")

        self._bot = self._build_bot()

        try:
            await self._bot.start(self._token)
        except asyncio.CancelledError:
            log.info("Discord client task cancelled")
            raise
        except Exception as e:
            log.error(f"Discord client crashed: {e}")
            raise
        finally:
            log.info("Discord client stopped")

    # --------------------------------------------------

    async def shutdown(self):
        """
        Gracefully close the Discord connection.
        """
        if not self._bot:
            return

        log.info("Closing Discord connection")

        try:
            await self._bot.close()
        except Exception as e:
            log.warning(f"Discord close error ignored: {e}")

        self._bot = None
        self._ready_event.clear()

    # --------------------------------------------------

    @property
    def bot(self) -> Optional[commands.Bot]:
        """
        Expose bot instance (read-only) for supervisor / status hooks.
        """
        return self._bot
