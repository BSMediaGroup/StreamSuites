"""
Discord Public Commands (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — NO OPERATIONAL BEHAVIOR YET.

This module defines user-facing (non-admin) command surfaces for the
Discord control-plane runtime.

Planned responsibilities:
- Public system status queries
- Livestream / platform visibility commands
- Read-only informational commands
- Safe commands callable by any guild member

IMPORTANT CONSTRAINTS:
- This module MUST NOT register commands on import
- This module MUST NOT own a Discord client
- This module MUST NOT perform permission checks directly
- This module MUST remain read-only and side-effect free
- All Discord objects must be passed in externally
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from shared.logging.logger import get_logger
from services.discord.logging import DiscordLogAdapter
from services.discord.heartbeat import DiscordHeartbeatState

log = get_logger("discord.commands.public", runtime="discord")


class PublicCommandHandler:
    """
    Declarative handler for public Discord commands.

    This class exposes safe, read-only command handlers intended for
    all users unless restricted upstream.
    """

    def __init__(
        self,
        *,
        logger: DiscordLogAdapter,
    ):
        self._logger = logger

    # --------------------------------------------------
    # GENERAL STATUS COMMANDS (PLACEHOLDERS)
    # --------------------------------------------------

    async def cmd_status(
        self,
        *,
        user_id: int,
        guild_id: int,
        heartbeat: Optional[DiscordHeartbeatState] = None,
    ) -> Dict[str, Any]:
        """
        Return basic system status.
        """

        snapshot = heartbeat.snapshot() if heartbeat else None

        self._logger.log_command(
            command="status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "system": "StreamSuites",
            "runtime": "discord",
            "heartbeat": snapshot,
        }

    async def cmd_uptime(
        self,
        *,
        user_id: int,
        guild_id: int,
        heartbeat: Optional[DiscordHeartbeatState] = None,
    ) -> Dict[str, Any]:
        """
        Return uptime information (placeholder).
        """

        started_at = (
            heartbeat.started_at.isoformat()
            if heartbeat and heartbeat.started_at
            else None
        )

        self._logger.log_command(
            command="uptime",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "started_at": started_at,
        }

    # --------------------------------------------------
    # LIVESTREAM / PLATFORM INFO (PLACEHOLDERS)
    # --------------------------------------------------

    async def cmd_latest(
        self,
        *,
        user_id: int,
        guild_id: int,
        platform: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return latest livestream or upload info (placeholder).
        """

        self._logger.log_command(
            command="latest",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"platform": platform},
        )

        return {
            "ok": True,
            "message": "Latest content lookup not implemented yet",
            "platform": platform,
        }

    # --------------------------------------------------
    # HELP / META
    # --------------------------------------------------

    async def cmd_help(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Return available public commands.
        """

        self._logger.log_command(
            command="help",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "commands": [
                "status",
                "uptime",
                "latest",
                "help",
            ],
        }
