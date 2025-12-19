"""
Discord Command Package (Control-Plane Runtime)

This package centralizes registration for all Discord command surfaces
used by the control-plane runtime.

Command categories:
- services   → bot / runtime service controls (status, toggles)
- admin      → administrator-only diagnostics and controls
- creators   → creator-scoped commands (future)
- public     → read-only public commands (future)

IMPORTANT DESIGN RULES:
- No command registration on import
- No Discord client ownership
- No side effects
- Explicit setup() calls only
"""

from __future__ import annotations

from discord.ext import commands

from shared.logging.logger import get_logger

# Sub-command modules (registration-only)
from services.discord.commands import services as service_commands
from services.discord.commands import admin_commands

log = get_logger("discord.commands", runtime="discord")


def setup(
    bot: commands.Bot,
    *,
    permissions,
    logger,
    status,
    supervisor=None,
):
    """
    Register all Discord command surfaces.

    This function is called exactly once by the Discord client
    during startup.
    """

    # --------------------------------------------------
    # Service-level commands
    # --------------------------------------------------
    service_commands.setup(bot)

    # --------------------------------------------------
    # Admin-level commands
    # --------------------------------------------------
    admin_commands.setup(
        bot,
        permissions=permissions,
        logger=logger,
        status=status,
        supervisor=supervisor,
    )

    # --------------------------------------------------
    # Creator commands (future)
    # --------------------------------------------------
    # creator_commands.setup(...)

    # --------------------------------------------------
    # Public commands (future)
    # --------------------------------------------------
    # public_commands.setup(...)

    log.info("Discord command surfaces initialized")
