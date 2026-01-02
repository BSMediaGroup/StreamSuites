"""Platform state definitions and helpers.

This module centralizes the runtime's interpretation of platform states.
States are intentionally minimal and dashboard-friendly:

- ACTIVE   : Platform should be scheduled and eligible for work
- PAUSED   : Platform is intentionally skipped but remains visible/telemetry-enabled
- DISABLED : Platform is fully disabled for the runtime session

The helpers here keep config ingestion backward-compatible while allowing
authoritative defaults for critical platforms (e.g., Rumble paused).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class PlatformState(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"

    @classmethod
    def from_value(
        cls, value: Any, *, default: "PlatformState" = None
    ) -> "PlatformState":
        if isinstance(value, cls):
            return value

        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if normalized in {member.name.lower(), member.value}:
                    return member

        if isinstance(value, bool):
            return cls.ACTIVE if value else cls.DISABLED

        return default or cls.DISABLED


# Authoritative defaults for well-known platforms during the resumed phase
DEFAULT_PLATFORM_STATES: Dict[str, PlatformState] = {
    "rumble": PlatformState.PAUSED,
    "youtube": PlatformState.ACTIVE,
    "twitch": PlatformState.ACTIVE,
    "kick": PlatformState.ACTIVE,
}


def normalize_platform_state(
    platform: str,
    raw_state: Any,
    *,
    enabled: bool = False,
) -> PlatformState:
    """Resolve a PlatformState using explicit values, defaults, and enable flags."""

    default_state = DEFAULT_PLATFORM_STATES.get(platform)
    if raw_state:
        return PlatformState.from_value(raw_state, default=default_state or PlatformState.DISABLED)

    if default_state:
        if default_state == PlatformState.ACTIVE and not enabled:
            return PlatformState.DISABLED
        return default_state

    return PlatformState.ACTIVE if enabled else PlatformState.DISABLED


def apply_default_platform_states(cfg: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Ensure default platform states exist for known platforms without overriding explicit config."""

    for platform, default_state in DEFAULT_PLATFORM_STATES.items():
        entry = cfg.setdefault(platform, {})
        state = entry.get("state")
        if not state:
            entry["state"] = default_state.value
        if default_state == PlatformState.PAUSED and not entry.get("paused_reason"):
            entry["paused_reason"] = "Platform ingestion paused"
    return cfg

