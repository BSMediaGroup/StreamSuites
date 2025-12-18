"""
Discord Admin Slash Command Registration (Control-Plane Runtime)

This module is the thin registration layer that exposes administrator-only
slash commands to Discord and delegates ALL logic to AdminCommandHandler.

Responsibilities:
- Register admin-only slash commands
- Perform permission gating via decorators
- Delegate execution to handler methods
- Perform Discord I/O (responses) ONLY at the boundary

IMPORTANT DESIGN RULES:
- NO business logic
- NO persistence
- NO runtime ownership
- NO Discord client creation
- Handler classes remain pure and testable
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from shared.logging.logger import get_logger

from services.discord.permissions import require_admin
from services.discord.commands.admin import AdminCommandHandler
from services.discord.logging import DiscordLogAdapter
from services.discord.permissions import DiscordPermissionResolver
from services.discord.status import DiscordStatusManager
from services.discord.runtime.supervisor import DiscordSupervisor

# NOTE: routed to Discord runtime log file
log = get_logger("discord.commands.admin.register", runtime="discord")


# ==================================================
# Registration Entry Point
# ==================================================

def setup(
    bot: commands.Bot,
    *,
    permissions: DiscordPermissionResolver,
    logger: DiscordLogAdapter,
    status: DiscordStatusManager,
    supervisor: DiscordSupervisor,
):
    """
    Register all admin-level Discord slash commands.

    This function is called explicitly by the Discord client
    during startup.
    """

    handler = AdminCommandHandler(
        permissions=permissions,
        logger=logger,
        status=status,
        supervisor=supervisor,
    )

    # --------------------------------------------------
    # /admin-runtime-status
    # --------------------------------------------------

    @app_commands.command(
        name="admin-runtime-status",
        description="Inspect Discord control-plane runtime status",
    )
    @require_admin()
    async def admin_runtime_status(
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=True)

        result = await handler.cmd_runtime_status(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )

        await interaction.followup.send(
            content=f"✅ Runtime: **{result['runtime']}**",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /admin-set-status
    # --------------------------------------------------

    @app_commands.command(
        name="admin-set-status",
        description="Set the Discord bot custom status",
    )
    @app_commands.describe(
        text="Status text to display",
        emoji="Optional emoji (unicode, no colons)",
    )
    @require_admin()
    async def admin_set_status(
        interaction: discord.Interaction,
        text: str,
        emoji: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        result = await handler.cmd_set_status(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            text=text,
            emoji=emoji,
        )

        await interaction.followup.send(
            content=f"✅ {result['message']}",
            ephemeral=True,
        )

    # --------------------------------------------------
    # /admin-clear-status
    # --------------------------------------------------

    @app_commands.command(
        name="admin-clear-status",
        description="Clear the Discord bot custom status",
    )
    @require_admin()
    async def admin_clear_status(
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=True)

        result = await handler.cmd_clear_status(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )

        await interaction.followup.send(
            content=f"✅ {result['message']}",
            ephemeral=True,
        )

    # --------------------------------------------------
    # Register Commands
    # --------------------------------------------------

    bot.tree.add_command(admin_runtime_status)
    bot.tree.add_command(admin_set_status)
    bot.tree.add_command(admin_clear_status)

    log.info("Discord admin slash commands registered")
