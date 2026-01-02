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
    "pilled": PlatformState.DISABLED,
}

# Read-only capability flags describing replay support per platform.
# These intentionally avoid any mutations so they can be reused in exports.
PLATFORM_REPLAY_CAPABILITIES: Dict[str, Dict[str, bool]] = {
    "youtube": {"replay_supported": True, "overlay_supported": True},
    "twitch": {"replay_supported": True, "overlay_supported": True},
    "kick": {"replay_supported": False, "overlay_supported": False},
    "rumble": {"replay_supported": True, "overlay_supported": True},
    "pilled": {"replay_supported": True, "overlay_supported": False},
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


def replay_capabilities(
    platform: str, state: PlatformState | str | None = None
) -> Dict[str, bool]:
    """Return replay and overlay capabilities for the given platform.

    Rumble (and any paused platform) is marked unsafe for replay while paused
    so dashboards do not treat paused ingestion as overlay-ready.
    """

    base = PLATFORM_REPLAY_CAPABILITIES.get(
        platform, {"replay_supported": False, "overlay_supported": False}
    )

    if state is not None:
        normalized = PlatformState.from_value(state, default=None)
        if normalized == PlatformState.PAUSED:
            return {"replay_supported": False, "overlay_supported": False}

    return dict(base)


__all__ = [
    "PlatformState",
    "DEFAULT_PLATFORM_STATES",
    "PLATFORM_REPLAY_CAPABILITIES",
    "normalize_platform_state",
    "apply_default_platform_states",
    "replay_capabilities",
]

