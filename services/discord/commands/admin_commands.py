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

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from shared.logging.logger import get_logger

from services.discord.permissions import require_admin
from services.discord.commands.admin import AdminCommandHandler
from services.discord.logging import DiscordLogAdapter
from services.discord.permissions import DiscordPermissionResolver
from services.discord.status import DiscordStatusManager
from services.discord.embeds import success_embed, error_embed, info_embed

if TYPE_CHECKING:
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
    supervisor: DiscordSupervisor | None = None,
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
        await interaction.response.defer(ephemeral=False)

        result = await handler.cmd_runtime_status(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )

        await interaction.followup.send(
            embed=info_embed(
                "Discord Runtime Status",
                f"Runtime: **{result['runtime']}**",
            ),
            ephemeral=False,
        )

    # --------------------------------------------------
    # /toggle
    # --------------------------------------------------

    @app_commands.command(
        name="toggle",
        description="Toggle a platform's live status on/off",
    )
    @app_commands.describe(
        platform="Platform name (e.g., twitch, youtube, rumble)",
    )
    @require_admin()
    async def toggle_platform(
        interaction: discord.Interaction,
        platform: str,
    ):
        await interaction.response.defer(ephemeral=False)

        result = await handler.cmd_toggle_platform(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            platform=platform,
        )

        embed = (
            success_embed("Platform Toggle", result["message"])
            if result.get("ok")
            else error_embed("Platform Toggle Failed", result["message"])
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

    # --------------------------------------------------
    # /trigger
    # --------------------------------------------------

    @app_commands.command(
        name="trigger",
        description="Manually fire a named trigger or pipeline event",
    )
    @app_commands.describe(
        name="Trigger name or command (e.g., clip)",
    )
    @require_admin()
    async def trigger(
        interaction: discord.Interaction,
        name: str,
    ):
        await interaction.response.defer(ephemeral=False)

        result = await handler.cmd_trigger(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            name=name,
        )

        embed = (
            success_embed("Trigger Executed", result["message"])
            if result.get("ok")
            else error_embed("Trigger Failed", result["message"])
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

    # --------------------------------------------------
    # /jobs
    # --------------------------------------------------

    @app_commands.command(
        name="jobs",
        description="List active and recent jobs in the runtime",
    )
    @require_admin()
    async def jobs(
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=False)

        result = await handler.cmd_jobs(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )

        active_jobs = result.get("active_jobs", [])
        if not active_jobs:
            message = "No active jobs at the moment."
        else:
            lines = []
            for job in active_jobs[:10]:
                job_id = str(job.get("id", ""))[:8]
                job_type = job.get("type", "unknown")
                status = job.get("status", "unknown")
                creator = job.get("creator_id", "unknown")
                lines.append(f"- {job_type} ({job_id}) [{status}] creator={creator}")
            message = (
                f"Active Jobs ({len(active_jobs)}):\n" + "\n".join(lines)
            )

        recent_count = result.get("recent_completed_count", 0)
        message += f"\nRecent completions (last hour): {recent_count}"

        embed = info_embed("Runtime Jobs", message)
        await interaction.followup.send(embed=embed, ephemeral=False)

    # --------------------------------------------------
    # /status
    # --------------------------------------------------

    @app_commands.command(
        name="status",
        description="Show a high-level StreamSuites system status summary",
    )
    @require_admin()
    async def status(
        interaction: discord.Interaction,
    ):
        await interaction.response.defer(ephemeral=False)

        result = await handler.cmd_status(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )

        platform_lines = result.get("platform_lines") or []
        platform_block = "\n".join(platform_lines) if platform_lines else "No platform data available."
        active_jobs = result.get("active_jobs", 0)
        generated_at = result.get("generated_at") or "unknown"

        message = (
            f"System Status (snapshot: {generated_at})\n"
            f"{platform_block}\n"
            f"Active jobs: {active_jobs}"
        )

        await interaction.followup.send(
            embed=info_embed("System Status", message),
            ephemeral=False,
        )

    # --------------------------------------------------
    # Register Commands
    # --------------------------------------------------

    bot.tree.add_command(admin_runtime_status)
    bot.tree.add_command(toggle_platform)
    bot.tree.add_command(trigger)
    bot.tree.add_command(jobs)
    bot.tree.add_command(status)

    log.info("Discord admin slash commands registered")
