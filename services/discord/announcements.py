"""
Discord Announcements Module (Control-Plane Runtime)

INTENTIONAL SCAFFOLD — NO OPERATIONAL BEHAVIOR YET.

This module will eventually handle outbound announcement delivery from the
Discord control-plane runtime to Discord servers.

Planned announcement targets include:
- Standard text channels
- Forum-style channels (thread creation + posting)
- Announcement / news channels
- Cross-post capable channels (future)

Planned announcement sources include:
- Streaming platform events (live, offline, uploads)
- Manual slash commands
- Scheduler / system status notifications
- Dashboard-triggered announcements

IMPORTANT CONSTRAINTS:
- This module MUST NOT register commands
- This module MUST NOT own a Discord client
- This module MUST NOT perform network I/O yet
- All Discord objects must be passed in externally when implemented
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from shared.logging.logger import get_logger

log = get_logger("discord.announcements", runtime="discord")


class DiscordAnnouncementManager:
    """
    Placeholder manager for Discord announcements.

    This class defines the future interface for sending announcements
    while remaining side-effect free until explicitly activated.
    """

    def __init__(self):
        self._enabled: bool = True

    # --------------------------------------------------
    # Control
    # --------------------------------------------------

    def enable(self):
        """Enable announcement delivery."""
        self._enabled = True
        log.debug("DiscordAnnouncementManager enabled")

    def disable(self):
        """Disable announcement delivery."""
        self._enabled = False
        log.debug("DiscordAnnouncementManager disabled")

    @property
    def enabled(self) -> bool:
        return self._enabled

    # --------------------------------------------------
    # Announcement Interfaces (NO-OP)
    # --------------------------------------------------

    async def announce(
        self,
        *,
        title: str,
        message: str,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        thread_name: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit an announcement.

        Parameters are accepted and logged, but no Discord API calls
        are made at this stage.
        """

        if not self._enabled:
            log.debug("Announcement skipped (disabled)")
            return

        payload = {
            "title": title,
            "message": message,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "thread_name": thread_name,
            "embed": embed,
            "metadata": metadata or {},
        }

        log.info(f"Discord announcement queued (noop): {payload}")

    # --------------------------------------------------
    # Convenience Hooks (Placeholders)
    # --------------------------------------------------

    async def announce_system_startup(self):
        """Placeholder for system startup announcement."""
        await self.announce(
            title="System Startup",
            message="Discord control-plane runtime started",
        )

    async def announce_system_shutdown(self):
        """Placeholder for system shutdown announcement."""
        await self.announce(
            title="System Shutdown",
            message="Discord control-plane runtime stopped",
        )

    async def announce_stream_event(
        self,
        *,
        platform: str,
        creator_id: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Placeholder for livestream-related announcements."""
        await self.announce(
            title=f"{platform.title()} Event",
            message=f"{creator_id}: {event}",
            metadata=details,
        )
