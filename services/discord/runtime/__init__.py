"""
Discord Runtime Package (Control-Plane)

This package defines the Discord control-plane runtime for StreamSuites.

It intentionally separates Discord lifecycle management from:
- streaming ingestion runtimes
- creator workers
- platform-specific execution logic

Contained responsibilities:
- Runtime supervision (start / stop orchestration)
- Lifecycle state tracking
- Heartbeat coordination
- Future control-plane utilities

IMPORTANT:
- Importing this package MUST NOT start the Discord client
- Importing this package MUST NOT create asyncio tasks
- All runtime execution is owned by DiscordSupervisor
"""

from services.discord.runtime.supervisor import DiscordSupervisor
from services.discord.runtime.lifecycle import DiscordRuntimeLifecycle

__all__ = [
    "DiscordSupervisor",
    "DiscordRuntimeLifecycle",
]
