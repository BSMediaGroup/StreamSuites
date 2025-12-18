"""
Discord Logging Adapter (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — NO ACTIVE BEHAVIOR YET.

This module defines a structured logging adapter for the Discord
control-plane runtime. It exists to normalize Discord-originated
events into formats consumable by:

- shared logging infrastructure
- dashboard status panels
- future external sinks (Wix, GitHub Pages, etc.)

PLANNED RESPONSIBILITIES (NOT YET IMPLEMENTED):
- Emit Discord lifecycle events in structured form
- Forward selected events to dashboard endpoints
- Support per-guild and per-command logging
- Integrate with permissions / admin config

IMPORTANT:
- This module MUST NOT send network requests yet
- This module MUST NOT depend on discord.py objects directly
- This module MUST remain side-effect free until activated
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from shared.logging.logger import get_logger

log = get_logger("discord.logging", runtime="discord")


class DiscordLogAdapter:
    """
    Placeholder adapter for Discord runtime logging.

    This class formalizes the interface for logging Discord-related
    events without committing to transport or persistence yet.
    """

    def __init__(self):
        self._enabled: bool = True

    # --------------------------------------------------
    # Lifecycle / Control
    # --------------------------------------------------

    def enable(self):
        """Enable Discord logging."""
        self._enabled = True
        log.debug("DiscordLogAdapter enabled")

    def disable(self):
        """Disable Discord logging."""
        self._enabled = False
        log.debug("DiscordLogAdapter disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # --------------------------------------------------
    # Structured Event Hooks (NO-OP)
    # --------------------------------------------------

    def log_event(
        self,
        *,
        event: str,
        level: str = "info",
        guild_id: Optional[int] = None,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Record a structured Discord event.

        Parameters are accepted but NOT forwarded anywhere yet.
        """

        if not self._enabled:
            return

        payload = {
            "event": event,
            "guild_id": guild_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "data": data or {},
        }

        # Local structured log only (no external emission)
        if level == "debug":
            log.debug(f"Discord event: {payload}")
        elif level == "warning":
            log.warning(f"Discord event: {payload}")
        elif level == "error":
            log.error(f"Discord event: {payload}")
        else:
            log.info(f"Discord event: {payload}")

    # --------------------------------------------------
    # Convenience Helpers (Placeholders)
    # --------------------------------------------------

    def log_startup(self):
        """Log Discord runtime startup."""
        self.log_event(event="discord_startup")

    def log_shutdown(self):
        """Log Discord runtime shutdown."""
        self.log_event(event="discord_shutdown")

    def log_command(
        self,
        *,
        command: str,
        guild_id: Optional[int],
        user_id: Optional[int],
        success: bool,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log a Discord slash/command execution."""
        self.log_event(
            event="discord_command",
            data={
                "command": command,
                "success": success,
                "extra": extra or {},
            },
            guild_id=guild_id,
            user_id=user_id,
        )
