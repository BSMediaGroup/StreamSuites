"""
Discord Client (Control-Plane Runtime)

This module owns the Discord connection itself.
It is intentionally minimal and lifecycle-focused.

Responsibilities:
- connect to Discord
- handle ready / resume / disconnect events
- load and register command surfaces
- expose a clean async run() / shutdown() contract
- emit structured logs for supervisor + dashboard use

IMPORTANT:
- This client MUST be controlled by DiscordSupervisor
- This client MUST NOT create its own event loop
- This client MUST NOT start streaming workers
"""

from __future__ import annotations

import os
import asyncio
from typing import Optional

import discord
from discord.ext import commands

from dotenv import load_dotenv

from shared.logging.logger import get_logger

from services.discord.status import DiscordStatusManager
from services.discord.logging import DiscordLogAdapter
from services.discord.permissions import DiscordPermissionResolver
from services.discord.heartbeat import DiscordHeartbeat
from services.discord.guild_logging import DiscordGuildLogDispatcher

# Command modules (registration only)
from services.discord.commands import services as service_commands
from services.discord.commands import admin_commands

# NOTE: routed to Discord runtime log file
log = get_logger("discord.client", runtime="discord")


class DiscordClient:
    """
    Thin wrapper around discord.py Bot.

    This class provides:
    - async run() entrypoint
    - async shutdown()
    - lifecycle event logging
    - command surface wiring
    """

    def __init__(self, supervisor=None):
        load_dotenv()

        token = (
            os.getenv("DISCORD_BOT_TOKEN")
            or os.getenv("DISCORD_CONTROL_BOT_TOKEN")
            or os.getenv("DISCORD_BOT_TOKEN_DANIEL")
        )
        if not token:
            raise RuntimeError(
                "Discord bot token not found in environment"
            )

        log.info(f"Discord bot token present: {bool(token)}")

        self._token: str = token
        self._guild_id: Optional[int] = self._load_guild_id()
        self._bot: Optional[commands.Bot] = None
        self._ready_event = asyncio.Event()
        self._supervisor = supervisor

        # --------------------------------------------------
        # Shared Discord services (singletons)
        # --------------------------------------------------
        self.status = DiscordStatusManager()
        self.logger = DiscordLogAdapter()
        self.permissions = DiscordPermissionResolver()
        self.heartbeat = DiscordHeartbeat()
        self.guild_logger = DiscordGuildLogDispatcher()

    # --------------------------------------------------

    @staticmethod
    def _load_guild_id() -> Optional[int]:
        raw = os.getenv("DISCORD_GUILD_ID")
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            log.warning(f"Invalid DISCORD_GUILD_ID value: {raw}")
            return None

    # --------------------------------------------------

    def _build_bot(self) -> commands.Bot:
        """
        Construct the discord.py Bot instance.

        NOTE:
        - Commands are registered here
        - No runtime ownership beyond Discord itself
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
        # Command Registration
        # --------------------------------------------------

        # Service-level commands
        service_commands.setup(bot)

        # Admin-level commands
        admin_commands.setup(
            bot,
            permissions=self.permissions,
            logger=self.logger,
            status=self.status,
            supervisor=self._supervisor,
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

            self.heartbeat.start()
            self.heartbeat.set_connected(True)

            # Apply persisted custom status
            try:
                await self.status.apply(bot)
            except Exception as e:
                log.warning(f"Failed to apply Discord status on ready: {e}")

            await self.guild_logger.log_startup(bot, event="startup")

            if self._supervisor:
                self._supervisor.notify_connected()

            # Sync slash commands
            try:
                if self._guild_id:
                    guild = discord.Object(id=self._guild_id)
                    bot.tree.copy_global_to(guild=guild)
                    await bot.tree.sync(guild=guild)
                    log.info(f"Discord command tree synced to guild {self._guild_id}")
                else:
                    await bot.tree.sync()
                    log.info("Discord command tree synced globally")
            except Exception as e:
                log.error(f"Failed to sync Discord commands: {e}")

            self._ready_event.set()

        @bot.event
        async def on_resumed():
            log.info("Discord connection resumed")
            self.heartbeat.set_connected(True)

            try:
                await self.status.apply(bot)
            except Exception as e:
                log.warning(f"Failed to re-apply Discord status on resume: {e}")

            if self._supervisor:
                self._supervisor.notify_connected()

            await self.guild_logger.log_startup(bot, event="reconnect")

        @bot.event
        async def on_disconnect():
            log.warning("Discord connection lost")
            self.heartbeat.set_connected(False)

            if self._supervisor:
                self._supervisor.notify_disconnected()

        @bot.event
        async def on_app_command_completion(interaction: discord.Interaction, command):
            await self.guild_logger.log_command(interaction, success=True)

        @bot.event
        async def on_app_command_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ):
            await self.guild_logger.log_command(
                interaction,
                success=False,
                error=str(error),
            )

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

        self.heartbeat.stop()

        self._bot = None
        self._ready_event.clear()

    # --------------------------------------------------

    @property
    def bot(self) -> Optional[commands.Bot]:
        """
        Expose bot instance (read-only) for supervisor hooks.
        """
        return self._bot
