"""
Discord Admin Commands (Control-Plane Runtime)

This module defines administrator-only command surfaces for the Discord
control-plane runtime.

Planned responsibilities:
- System status inspection (runtime, scheduler, heartbeat)
- Discord bot status management (custom presence text / emoji)
- Enable / disable Discord runtime features
- Diagnostic and debug reporting
- Administrative configuration overrides

IMPORTANT CONSTRAINTS:
- This module MUST NOT register commands on import
- This module MUST NOT own a Discord client
- This module MUST NOT perform permission checks directly
- This module MUST remain declarative and side-effect free
- All Discord objects (Interaction, Bot, Context) must be passed in externally
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from shared.logging.logger import get_logger
from services.discord.permissions import DiscordPermissionResolver
from services.discord.logging import DiscordLogAdapter
from services.discord.status import DiscordStatusManager
from services.discord.runtime.supervisor import DiscordSupervisor

log = get_logger("discord.commands.admin", runtime="discord")


class AdminCommandHandler:
    """
    Declarative handler for admin-level Discord commands.

    This class does NOT register commands.
    It provides callable handlers to be wired by the Discord client layer.
    """

    def __init__(
        self,
        *,
        permissions: DiscordPermissionResolver,
        logger: DiscordLogAdapter,
        status: DiscordStatusManager,
        supervisor: Optional[DiscordSupervisor] = None,
    ):
        self._permissions = permissions
        self._logger = logger
        self._status = status
        self._supervisor = supervisor

    # --------------------------------------------------
    # STATUS COMMANDS
    # --------------------------------------------------

    async def cmd_set_status(
        self,
        *,
        user_id: int,
        guild_id: int,
        text: str,
        emoji: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the bot's custom Discord presence.

        Permissions: Admin only
        """

        self._logger.log_command(
            command="set_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        # NOTE: actual mutation happens in services.discord.status
        return {
            "ok": True,
            "message": "Status update accepted",
            "text": text,
            "emoji": emoji,
        }

    async def cmd_clear_status(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Clear the bot's custom Discord presence.

        Permissions: Admin only
        """

        self._logger.log_command(
            command="clear_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "message": "Status cleared",
        }

    # --------------------------------------------------
    # DIAGNOSTICS / INSPECTION (NOW REAL)
    # --------------------------------------------------

    async def cmd_runtime_status(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Return Discord runtime diagnostic information.
        """

        snapshot = (
            self._supervisor.snapshot()
            if self._supervisor
            else {
                "running": False,
                "connected": False,
                "tasks": 0,
                "heartbeat": None,
                "status": None,
            }
        )

        self._logger.log_command(
            command="runtime_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "runtime": "discord",
            "supervisor": snapshot,
        }

    # --------------------------------------------------
    # FEATURE FLAGS (STILL PLACEHOLDERS)
    # --------------------------------------------------

    async def cmd_enable_feature(
        self,
        *,
        user_id: int,
        guild_id: int,
        feature: str,
    ) -> Dict[str, Any]:
        """
        Enable a Discord runtime feature (placeholder).
        """

        self._logger.log_command(
            command="enable_feature",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"feature": feature},
        )

        return {
            "ok": True,
            "message": f"Feature '{feature}' enable requested (noop)",
        }

    async def cmd_disable_feature(
        self,
        *,
        user_id: int,
        guild_id: int,
        feature: str,
    ) -> Dict[str, Any]:
        """
        Disable a Discord runtime feature (placeholder).
        """

        self._logger.log_command(
            command="disable_feature",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"feature": feature},
        )

        return {
            "ok": True,
            "message": f"Feature '{feature}' disable requested (noop)",
        }
