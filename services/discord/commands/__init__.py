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
# admin / creators / public will be wired later

log = get_logger("discord.commands", runtime="discord")


def setup(bot: commands.Bot):
    """
    Register all Discord command surfaces.

    This function is called exactly once by the Discord client
    during startup.
    """

    # --------------------------------------------------
    # Service-level commands (ACTIVE)
    # --------------------------------------------------
    service_commands.setup(bot)

    # --------------------------------------------------
    # Admin commands (future registration)
    # --------------------------------------------------
    # admin_commands.setup(bot)

    # --------------------------------------------------
    # Creator commands (future registration)
    # --------------------------------------------------
    # creator_commands.setup(bot)

    # --------------------------------------------------
    # Public commands (future registration)
    # --------------------------------------------------
    # public_commands.setup(bot)

    log.info("Discord command surfaces initialized")
