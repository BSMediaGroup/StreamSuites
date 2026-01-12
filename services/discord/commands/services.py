"""
Discord Service Commands

This module defines control-plane slash commands related to
Discord runtime services, including bot status management.

Responsibilities:
- Register slash commands (no runtime ownership)
- Delegate logic to service modules (status, logging, etc.)
- Enforce permission checks (admin / service-level)

IMPORTANT:
- This module does NOT start the Discord client
- This module does NOT own persistence directly
- All side effects are delegated to services.discord.*
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from shared.logging.logger import get_logger
from shared.config.discord import (
    get_guild_config,
    notification_channel_keys,
    notification_label,
    update_guild_config,
)
from services.discord.status import DiscordStatusManager
from services.discord.permissions import require_admin
from services.discord.embeds import success_embed, error_embed, info_embed

# NOTE: routed to Discord runtime log file
log = get_logger("discord.commands.services", runtime="discord")


# --------------------------------------------------
# Command Registration Helper
# --------------------------------------------------

def setup(bot: commands.Bot):
    """
    Register service-level slash commands.
    Called by Discord client during command loading.
    """
    bot.tree.add_command(bot_status)
    bot.tree.add_command(logging_set_channel)
    bot.tree.add_command(logging_enable)
    bot.tree.add_command(logging_disable)
    bot.tree.add_command(notifications_set)
    bot.tree.add_command(dashboard)
    bot.tree.add_command(help)
    bot.tree.add_command(list_commands)
    log.info("Discord service commands registered")


# --------------------------------------------------
# /bot-status
# --------------------------------------------------

@app_commands.command(
    name="bot-status",
    description="Set a custom status message for the Discord bot",
)
@app_commands.describe(
    text="Status text to display",
    emoji="Optional emoji (unicode, no colons)",
)
@require_admin()
async def bot_status(
    interaction: discord.Interaction,
    text: str,
    emoji: str | None = None,
):
    """
    Update the Discord bot custom presence.

    This command:
    - persists status to shared state
    - applies status immediately if bot is connected
    """

    await interaction.response.defer(ephemeral=False)

    status = DiscordStatusManager()

    try:
        await status.set_status(
            text=text,
            emoji=emoji,
            bot=interaction.client,
        )
    except Exception as e:
        log.error(f"Failed to set Discord status: {e}")
        await interaction.followup.send(
            embed=error_embed(
                "Bot status update failed",
                "Failed to update bot status. Check logs.",
            ),
            ephemeral=False,
        )
        return

    message = f"Bot status updated to: **{text}**"
    if emoji:
        message += f" {emoji}"

    log.info(
        f"Bot status updated by {interaction.user} "
        f"text={text!r} emoji={emoji!r}"
    )

    await interaction.followup.send(
        embed=success_embed("Bot Status Updated", message),
        ephemeral=False,
    )


# --------------------------------------------------
# /logging-set-channel
# --------------------------------------------------

@app_commands.command(
    name="logging-set-channel",
    description="Set the logging channel for this guild",
)
@app_commands.describe(
    channel="Channel to receive bot logs",
)
@require_admin()
async def logging_set_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
):
    if not interaction.guild:
        await interaction.response.send_message(
            embed=error_embed("Guild required", "This command must be used in a guild."),
            ephemeral=False,
        )
        return

    update_guild_config(
        interaction.guild.id,
        {"logging": {"channel_id": channel.id}},
    )

    await interaction.response.send_message(
        embed=success_embed(
            "Logging Channel Set",
            f"Logging channel updated to {channel.mention}.",
        ),
        ephemeral=False,
    )


# --------------------------------------------------
# /logging-enable
# --------------------------------------------------

@app_commands.command(
    name="logging-enable",
    description="Enable Discord bot logging for this guild",
)
@require_admin()
async def logging_enable(
    interaction: discord.Interaction,
):
    if not interaction.guild:
        await interaction.response.send_message(
            embed=error_embed("Guild required", "This command must be used in a guild."),
            ephemeral=False,
        )
        return

    current = get_guild_config(interaction.guild.id)
    logging = current.get("logging", {})
    if not logging.get("channel_id"):
        await interaction.response.send_message(
            embed=error_embed(
                "Logging channel missing",
                "Set a logging channel first with /logging-set-channel.",
            ),
            ephemeral=False,
        )
        return

    update_guild_config(interaction.guild.id, {"logging": {"enabled": True}})
    await interaction.response.send_message(
        embed=success_embed("Logging Enabled", "Discord bot logging is now enabled."),
        ephemeral=False,
    )


# --------------------------------------------------
# /logging-disable
# --------------------------------------------------

@app_commands.command(
    name="logging-disable",
    description="Disable Discord bot logging for this guild",
)
@require_admin()
async def logging_disable(
    interaction: discord.Interaction,
):
    if not interaction.guild:
        await interaction.response.send_message(
            embed=error_embed("Guild required", "This command must be used in a guild."),
            ephemeral=False,
        )
        return

    update_guild_config(interaction.guild.id, {"logging": {"enabled": False}})
    await interaction.response.send_message(
        embed=success_embed("Logging Disabled", "Discord bot logging is now disabled."),
        ephemeral=False,
    )


# --------------------------------------------------
# /notifications-set
# --------------------------------------------------

@app_commands.command(
    name="notifications-set",
    description="Set a notification channel for this guild",
)
@app_commands.describe(
    type="Notification category",
    channel="Channel to receive notifications",
)
@app_commands.choices(
    type=[
        app_commands.Choice(name=notification_label(key), value=key)
        for key in notification_channel_keys()
    ]
)
@require_admin()
async def notifications_set(
    interaction: discord.Interaction,
    type: app_commands.Choice[str],
    channel: discord.TextChannel,
):
    if not interaction.guild:
        await interaction.response.send_message(
            embed=error_embed("Guild required", "This command must be used in a guild."),
            ephemeral=False,
        )
        return

    update_guild_config(
        interaction.guild.id,
        {"notifications": {type.value: channel.id}},
    )

    await interaction.response.send_message(
        embed=success_embed(
            "Notification Channel Set",
            f"{type.name} notifications will post to {channel.mention}.",
        ),
        ephemeral=False,
    )


# --------------------------------------------------
# /dashboard
# --------------------------------------------------

@app_commands.command(
    name="dashboard",
    description="Get the StreamSuites dashboard link",
)
async def dashboard(
    interaction: discord.Interaction,
):
    await interaction.response.send_message(
        embed=info_embed(
            "StreamSuites Dashboard",
            "[Open the dashboard](https://dashboard.streamsuites.app)",
        ),
        ephemeral=False,
    )


# --------------------------------------------------
# /help
# --------------------------------------------------

@app_commands.command(
    name="help",
    description="Get support links for StreamSuites",
)
async def help(
    interaction: discord.Interaction,
):
    description = (
        "[Discord support channel]"
        "(https://discord.com/channels/1449303974086967306/1449303975890260021)\n"
        "[Web support](https://support.streamsuites.online)"
    )
    await interaction.response.send_message(
        embed=info_embed("StreamSuites Support", description),
        ephemeral=False,
    )


# --------------------------------------------------
# /list-commands
# --------------------------------------------------

@app_commands.command(
    name="list-commands",
    description="List all available slash commands",
)
async def list_commands(
    interaction: discord.Interaction,
):
    if not interaction.client:
        await interaction.response.send_message(
            embed=error_embed("Command registry unavailable", "Discord client missing."),
            ephemeral=False,
        )
        return

    commands_list = sorted(
        interaction.client.tree.get_commands(),
        key=lambda cmd: cmd.name,
    )

    lines = [
        f"/{cmd.name} — {cmd.description or 'No description'}"
        for cmd in commands_list
    ]

    description = "\n".join(lines) if lines else "No commands registered."
    await interaction.response.send_message(
        embed=info_embed("Available Slash Commands", description),
        ephemeral=False,
    )
