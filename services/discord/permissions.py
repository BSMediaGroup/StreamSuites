"""
Discord Permissions Module (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — NO OPERATIONAL BEHAVIOR YET.

This module will define and enforce permission rules for the Discord
control-plane runtime.

Planned responsibilities:
- Resolve guild-specific configuration (admin roles, channels, overrides)
- Validate whether a user may execute a given command
- Centralize permission logic so commands remain declarative
- Support dashboard-driven permission updates (future)
- Support multi-guild installations safely

IMPORTANT CONSTRAINTS:
- This module MUST NOT register Discord commands
- This module MUST NOT own a Discord client
- This module MUST NOT perform Discord API calls directly
- All Discord objects (Interaction, Member, Guild) must be passed in externally
"""

from __future__ import annotations

from typing import Optional, Iterable, Dict, Any

from shared.logging.logger import get_logger

log = get_logger("discord.permissions", runtime="discord")


class PermissionResult:
    """
    Structured permission check result.

    This allows commands and supervisors to handle permissions consistently
    without duplicating messaging or logic.
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

        All logic is currently permissive and logged only.
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
