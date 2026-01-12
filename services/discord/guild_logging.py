from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord

from shared.config.discord import get_guild_config
from shared.logging.logger import get_logger
from services.discord.embeds import info_embed, error_embed

log = get_logger("discord.guild_logging", runtime="discord")


class DiscordGuildLogDispatcher:
    def __init__(self) -> None:
        self._logger = log

    @staticmethod
    def _resolve_bot_status(bot: discord.Client) -> str:
        presence = getattr(bot, "status", None)
        activity = getattr(bot, "activity", None)
        presence_text = str(presence) if presence else "unknown"
        activity_text = activity.name if activity and getattr(activity, "name", None) else "none"
        return f"{presence_text} • {activity_text}"

    @staticmethod
    def _parse_command_args(interaction: discord.Interaction) -> Dict[str, Any]:
        data = interaction.data or {}
        options = data.get("options", [])

        def parse_options(raw: list[Dict[str, Any]]) -> Dict[str, Any]:
            parsed: Dict[str, Any] = {}
            for option in raw:
                name = option.get("name")
                if not name:
                    continue
                if option.get("type") in (1, 2):
                    parsed[name] = parse_options(option.get("options", []))
                else:
                    parsed[name] = option.get("value")
            return parsed

        if isinstance(options, list):
            return parse_options(options)
        return {}

    async def log_startup(self, bot: discord.Client, *, event: str) -> None:
        if not bot.guilds:
            return

        embed = info_embed(
            title="Discord Bot Connected" if event == "startup" else "Discord Bot Reconnected",
            description=f"Event: {event}",
        )
        embed.timestamp = datetime.now(timezone.utc)
        embed.add_field(name="Timestamp (UTC)", value=embed.timestamp.isoformat(), inline=False)
        embed.add_field(name="Connected guilds", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Bot status", value=self._resolve_bot_status(bot), inline=False)

        for guild in bot.guilds:
            await self._send_guild_log(guild, embed)

    async def log_command(
        self,
        interaction: discord.Interaction,
        *,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        if not interaction.guild or not interaction.user:
            return

        guild = interaction.guild
        embed = info_embed(title="Slash Command Executed")
        embed.timestamp = datetime.now(timezone.utc)

        command_name = interaction.command.qualified_name if interaction.command else "unknown"
        args = self._parse_command_args(interaction)
        args_text = json.dumps(args, ensure_ascii=False, indent=2) if args else "None"

        embed.add_field(name="Command", value=command_name, inline=False)
        embed.add_field(name="Arguments", value=args_text, inline=False)
        embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        embed.add_field(name="Guild", value=f"{guild.name} ({guild.id})", inline=False)
        embed.add_field(name="Result", value="Success" if success else "Failed", inline=True)

        if error:
            embed.add_field(name="Error", value=error[:900], inline=False)

        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url,
        )

        await self._send_guild_log(guild, embed)

    async def _send_guild_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        config = get_guild_config(guild.id)
        if not config.get("logging_enabled"):
            return

        channel_id = config.get("logging_channel_id")
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.NotFound:
                self._logger.warning(
                    f"Logging channel {channel_id} not found in guild {guild.id}"
                )
                return
            except discord.Forbidden:
                self._logger.warning(
                    f"No access to logging channel {channel_id} in guild {guild.id}"
                )
                return
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.warning(
                    f"Failed to fetch logging channel {channel_id} in guild {guild.id}: {exc}"
                )
                return

        if not isinstance(channel, discord.abc.Messageable):
            self._logger.warning(
                f"Logging channel {channel_id} in guild {guild.id} is not messageable"
            )
            return

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            self._logger.warning(
                f"No permissions to send logs to channel {channel_id} in guild {guild.id}"
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning(
                f"Failed to send log to channel {channel_id} in guild {guild.id}: {exc}"
            )

    async def log_startup_failure(
        self,
        bot: discord.Client,
        *,
        error_message: str,
    ) -> None:
        embed = error_embed("Discord Bot Startup Error", error_message)
        embed.timestamp = datetime.now(timezone.utc)
        for guild in bot.guilds:
            await self._send_guild_log(guild, embed)
