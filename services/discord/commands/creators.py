"""
Discord Creator Commands (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — NO OPERATIONAL BEHAVIOR YET.

This module defines creator-scoped command handlers for the Discord
control-plane runtime.

Creator commands sit between:
- public commands (read-only, everyone)
- admin commands (guild/system administration)

Planned responsibilities:
- Creator ownership verification (future)
- Linking Discord guilds to creators
- Querying creator runtime status
- Triggering creator-scoped actions (future)

IMPORTANT CONSTRAINTS:
- This module MUST NOT register Discord commands
- This module MUST NOT own a Discord client
- This module MUST NOT perform permission checks directly
- Creator ownership validation is delegated to permissions layer
- All Discord objects must be passed in externally
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from shared.logging.logger import get_logger
from services.discord.logging import DiscordLogAdapter
from services.discord.heartbeat import DiscordHeartbeatState

log = get_logger("discord.commands.creators", runtime="discord")


class CreatorCommandHandler:
    """
    Declarative handler for creator-scoped Discord commands.

    These commands are intended for:
    - creator owners
    - delegated moderators (future)
    - dashboard-authenticated users (future)
    """

    def __init__(
        self,
        *,
        logger: DiscordLogAdapter,
    ):
        self._logger = logger

    # --------------------------------------------------
    # CREATOR DISCOVERY / STATUS (PLACEHOLDERS)
    # --------------------------------------------------

    async def cmd_creator_status(
        self,
        *,
        user_id: int,
        guild_id: int,
        creator_id: str,
        heartbeat: Optional[DiscordHeartbeatState] = None,
    ) -> Dict[str, Any]:
        """
        Return status information for a specific creator.
        """

        snapshot = heartbeat.snapshot() if heartbeat else None

        self._logger.log_command(
            command="creator_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"creator_id": creator_id},
        )

        return {
            "ok": True,
            "creator_id": creator_id,
            "runtime": "unknown",
            "heartbeat": snapshot,
        }

    async def cmd_creator_uptime(
        self,
        *,
        user_id: int,
        guild_id: int,
        creator_id: str,
        heartbeat: Optional[DiscordHeartbeatState] = None,
    ) -> Dict[str, Any]:
        """
        Return uptime information for a creator runtime (placeholder).
        """

        started_at = (
            heartbeat.started_at.isoformat()
            if heartbeat and heartbeat.started_at
            else None
        )

        self._logger.log_command(
            command="creator_uptime",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"creator_id": creator_id},
        )

        return {
            "ok": True,
            "creator_id": creator_id,
            "started_at": started_at,
        }

    # --------------------------------------------------
    # CREATOR LINKING / ASSOCIATION (STUBS)
    # --------------------------------------------------

    async def cmd_link_creator(
        self,
        *,
        user_id: int,
        guild_id: int,
        creator_id: str,
    ) -> Dict[str, Any]:
        """
        Placeholder for linking a Discord guild to a creator.
        """

        self._logger.log_command(
            command="link_creator",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"creator_id": creator_id},
        )

        return {
            "ok": True,
            "message": "Creator linking not implemented yet",
            "creator_id": creator_id,
        }

    async def cmd_unlink_creator(
        self,
        *,
        user_id: int,
        guild_id: int,
        creator_id: str,
    ) -> Dict[str, Any]:
        """
        Placeholder for unlinking a Discord guild from a creator.
        """

        self._logger.log_command(
            command="unlink_creator",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"creator_id": creator_id},
        )

        return {
            "ok": True,
            "message": "Creator unlinking not implemented yet",
            "creator_id": creator_id,
        }

    # --------------------------------------------------
    # META
    # --------------------------------------------------

    async def cmd_creator_help(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Return available creator-scoped commands.
        """

        self._logger.log_command(
            command="creator_help",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "commands": [
                "creator_status",
                "creator_uptime",
                "link_creator",
                "unlink_creator",
            ],
        }
