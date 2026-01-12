"""
Discord Permissions Module (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — MINIMAL OPERATIONAL BEHAVIOR ENABLED.

This module defines and enforces permission rules for the Discord
control-plane runtime.

Current behavior:
- Provides an app_commands-compatible admin check
- Uses Discord-native permission flags only
- Resolver remains passive and future-ready

IMPORTANT CONSTRAINTS:
- This module MUST NOT own a Discord client
- This module MUST NOT perform network I/O
- This module MUST remain centrally authoritative for permission logic
"""

from __future__ import annotations

from typing import Optional, Iterable, Dict, Any, Callable, Awaitable

import discord
from discord import app_commands

from shared.config.discord import is_discord_admin
from shared.logging.logger import get_logger

log = get_logger("discord.permissions", runtime="discord")


# ==================================================
# Structured Permission Result
# ==================================================

class PermissionResult:
    """
    Structured permission check result.

    Allows commands and supervisors to handle permissions
    consistently without duplicating logic.
    """

    def __init__(
        self,
        allowed: bool,
        *,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.metadata = metadata or {}

    def __bool__(self) -> bool:
        return self.allowed


# ==================================================
# Passive Resolver (Future Dashboard / Config Use)
# ==================================================

class DiscordPermissionResolver:
    """
    Central permission resolver for Discord control-plane operations.

    This class is intentionally passive:
    - No Discord API calls
    - No side effects
    - Accepts raw IDs and config snapshots only
    """

    def __init__(self):
        self._enabled: bool = True

    # --------------------------------------------------
    # Control
    # --------------------------------------------------

    def enable(self):
        """Enable permission enforcement."""
        self._enabled = True
        log.debug("DiscordPermissionResolver enabled")

    def disable(self):
        """Disable permission enforcement (allow all)."""
        self._enabled = False
        log.warning("DiscordPermissionResolver disabled (allow-all mode)")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # --------------------------------------------------
    # Core Permission Checks (PLACEHOLDERS)
    # --------------------------------------------------

    def can_execute_command(
        self,
        *,
        user_id: int,
        guild_id: int,
        command_name: str,
        user_roles: Optional[Iterable[int]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """
        Determine whether a user may execute a command.

        Currently permissive (noop).
        """

        if not self._enabled:
            return PermissionResult(True)

        log.debug(
            "Permission check (noop)",
            extra={
                "user_id": user_id,
                "guild_id": guild_id,
                "command": command_name,
                "roles": list(user_roles or []),
            },
        )

        return PermissionResult(
            True,
            metadata={
                "mode": "noop",
                "command": command_name,
            },
        )

    # --------------------------------------------------
    # Convenience Policies (STUBS)
    # --------------------------------------------------

    def require_admin(
        self,
        *,
        user_id: int,
        guild_id: int,
        user_roles: Optional[Iterable[int]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """
        Placeholder for admin-only enforcement.
        """
        return self.can_execute_command(
            user_id=user_id,
            guild_id=guild_id,
            command_name="__admin__",
            user_roles=user_roles,
            config=config,
        )

    def require_creator_owner(
        self,
        *,
        user_id: int,
        creator_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> PermissionResult:
        """
        Placeholder for creator-owner enforcement.
        """
        log.debug(
            "Creator-owner permission check (noop)",
            extra={
                "user_id": user_id,
                "creator_id": creator_id,
            },
        )
        return PermissionResult(True, metadata={"mode": "noop"})


# ==================================================
# app_commands Decorators (ACTIVE LAYER)
# ==================================================

def require_admin() -> Callable[[Callable[..., Awaitable[Any]]], Any]:
    """
    Discord slash-command check: admin-only.

    CURRENT IMPLEMENTATION:
    - Uses Discord-native administrator permission
    - Allows guild owner implicitly
    - Emits clean ephemeral error on failure

    FUTURE:
    - Delegate to DiscordPermissionResolver
    - Dashboard-configurable admin roles
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not interaction.user:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True,
            )
            return False

        member = interaction.user
        guild = interaction.guild

        is_admin = (
            guild.owner_id == member.id
            or member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
        )
        admin_override = is_discord_admin(str(member.id))

        if not is_admin and not admin_override:
            log.warning(
                f"Admin permission denied: "
                f"user={member.id} guild={guild.id}"
            )
            await interaction.response.send_message(
                "❌ You must be a server administrator to use this command.",
                ephemeral=True,
            )
            return False

        if admin_override and not is_admin:
            log.info(
                "Admin override granted for Discord user=%s guild=%s",
                member.id,
                guild.id,
            )

        return True

    return app_commands.check(predicate)
