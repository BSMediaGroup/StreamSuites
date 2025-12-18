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
from services.discord.status import DiscordStatusManager
from services.discord.permissions import require_admin

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

    await interaction.response.defer(ephemeral=True)

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
            "❌ Failed to update bot status. Check logs.",
            ephemeral=True,
        )
        return

    message = f"✅ Bot status updated to: **{text}**"
    if emoji:
        message += f" {emoji}"

    log.info(
        f"Bot status updated by {interaction.user} "
        f"text={text!r} emoji={emoji!r}"
    )

    await interaction.followup.send(message, ephemeral=True)
