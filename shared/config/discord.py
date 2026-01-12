"""
Discord configuration loader for per-guild settings.

Design rules:
- Import-safe (no side effects)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from shared.logging.logger import get_logger

log = get_logger("shared.config.discord")

_CONFIG_PATH = Path(__file__).parent / "discord.json"

NOTIFICATION_CHANNEL_LABELS: Dict[str, str] = {
    "general": "General",
    "rumble_clips": "Rumble clips",
    "youtube_clips": "YouTube clips",
    "kick_clips": "Kick clips",
    "pilled_clips": "Pilled clips",
    "twitch_clips": "Twitch clips",
}
NOTIFICATION_CHANNEL_KEYS = tuple(NOTIFICATION_CHANNEL_LABELS.keys())

LEGACY_NOTIFICATION_MAP = {
    "notifications_general": "general",
    "notifications_rumble_clips": "rumble_clips",
    "notifications_youtube_clips": "youtube_clips",
    "notifications_kick_clips": "kick_clips",
    "notifications_pilled_clips": "pilled_clips",
    "notifications_twitch_clips": "twitch_clips",
}

_DEFAULT_LOGGING_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "channel_id": None,
}

_DEFAULT_NOTIFICATIONS: Dict[str, Any] = {
    key: None for key in NOTIFICATION_CHANNEL_KEYS
}

_DEFAULT_GUILD_CONFIG: Dict[str, Any] = {
    "logging": dict(_DEFAULT_LOGGING_CONFIG),
    "notifications": dict(_DEFAULT_NOTIFICATIONS),
}


def _normalize_channel_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return raw
    return None


def _normalize_guild_config(raw: Any) -> Dict[str, Any]:
    data = {
        "logging": dict(_DEFAULT_LOGGING_CONFIG),
        "notifications": dict(_DEFAULT_NOTIFICATIONS),
    }
    if not isinstance(raw, dict):
        return data

    logging_raw = raw.get("logging")
    if isinstance(logging_raw, dict):
        logging_enabled = logging_raw.get("enabled")
        if isinstance(logging_enabled, bool):
            data["logging"]["enabled"] = logging_enabled
        if "channel_id" in logging_raw:
            data["logging"]["channel_id"] = _normalize_channel_id(logging_raw.get("channel_id"))

    logging_enabled = raw.get("logging_enabled")
    if isinstance(logging_enabled, bool):
        data["logging"]["enabled"] = logging_enabled

    if "logging_channel_id" in raw:
        data["logging"]["channel_id"] = _normalize_channel_id(raw.get("logging_channel_id"))

    notifications_raw = raw.get("notifications")
    if isinstance(notifications_raw, dict):
        for key, value in notifications_raw.items():
            data["notifications"][key] = _normalize_channel_id(value)

    for legacy_key, notification_key in LEGACY_NOTIFICATION_MAP.items():
        if legacy_key in raw:
            data["notifications"][notification_key] = _normalize_channel_id(raw.get(legacy_key))

    return data


def load_discord_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = path or _CONFIG_PATH

    if not config_path.exists():
        return {"discord": {"guilds": {}}}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Failed to load discord config ({exc}); using defaults")
        return {"discord": {"guilds": {}}}

    if not isinstance(data, dict):
        return {"discord": {"guilds": {}}}

    discord_root = data.get("discord", {})
    if isinstance(discord_root, dict):
        guilds_raw = discord_root.get("guilds", {})
    else:
        guilds_raw = data.get("guilds", {})
    guilds: Dict[str, Any] = {}

    if isinstance(guilds_raw, dict):
        for guild_id, entry in guilds_raw.items():
            if not isinstance(entry, dict):
                continue
            guilds[str(guild_id)] = _normalize_guild_config(entry)

    return {"discord": {"guilds": guilds}}


def save_discord_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    config_path = path or _CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    discord_root = config.get("discord", {}) if isinstance(config, dict) else {}
    if isinstance(discord_root, dict):
        guilds = discord_root.get("guilds", {})
    else:
        guilds = config.get("guilds", {}) if isinstance(config, dict) else {}

    payload = {"discord": {"guilds": guilds if isinstance(guilds, dict) else {}}}
    config_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False),
        encoding="utf-8",
    )


def get_guild_config(
    guild_id: int,
    config: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    config = config or load_discord_config(path)
    discord_root = config.get("discord", {}) if isinstance(config, dict) else {}
    if isinstance(discord_root, dict):
        guilds = discord_root.get("guilds", {})
    else:
        guilds = config.get("guilds", {}) if isinstance(config, dict) else {}
    entry = guilds.get(str(guild_id), {})
    return _normalize_guild_config(entry)


def update_guild_config(
    guild_id: int,
    updates: Dict[str, Any],
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    config = load_discord_config(path)
    discord_root = config.setdefault("discord", {})
    guilds = discord_root.setdefault("guilds", {})

    current = _normalize_guild_config(guilds.get(str(guild_id), {}))

    for key, value in updates.items():
        if key == "logging" and isinstance(value, dict):
            logging_enabled = value.get("enabled")
            if isinstance(logging_enabled, bool):
                current["logging"]["enabled"] = logging_enabled
            if "channel_id" in value:
                current["logging"]["channel_id"] = _normalize_channel_id(value.get("channel_id"))
            continue

        if key == "notifications" and isinstance(value, dict):
            for notification_key, notification_value in value.items():
                current["notifications"][notification_key] = _normalize_channel_id(notification_value)
            continue

        if key == "logging_enabled":
            if isinstance(value, bool):
                current["logging"]["enabled"] = value
            continue

        if key == "logging_channel_id":
            current["logging"]["channel_id"] = _normalize_channel_id(value)
            continue

        if key in LEGACY_NOTIFICATION_MAP:
            current["notifications"][LEGACY_NOTIFICATION_MAP[key]] = _normalize_channel_id(value)

    guilds[str(guild_id)] = current
    save_discord_config(config, path)
    return current


def default_guild_config() -> Dict[str, Any]:
    return _normalize_guild_config({})


def notification_channel_keys() -> tuple[str, ...]:
    return NOTIFICATION_CHANNEL_KEYS


def notification_label(key: str) -> str:
    return NOTIFICATION_CHANNEL_LABELS.get(key, key.replace("_", " ").title())


def parse_channel_id(value: Any) -> Optional[int]:
    normalized = _normalize_channel_id(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def validate_discord_config(config: Dict[str, Any]) -> bool:
    if not isinstance(config, dict):
        return False

    discord_root = config.get("discord", {})
    if discord_root is None:
        return True
    if not isinstance(discord_root, dict):
        return False

    guilds = discord_root.get("guilds", {})
    if guilds is None:
        return True
    if not isinstance(guilds, dict):
        return False

    for entry in guilds.values():
        if not isinstance(entry, dict):
            continue
        logging_raw = entry.get("logging")
        if logging_raw is not None:
            if not isinstance(logging_raw, dict):
                return False
            enabled = logging_raw.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                return False
            channel_id = logging_raw.get("channel_id")
            if channel_id is not None and not isinstance(channel_id, str):
                return False
        notifications_raw = entry.get("notifications")
        if notifications_raw is not None:
            if not isinstance(notifications_raw, dict):
                return False
            for value in notifications_raw.values():
                if value is not None and not isinstance(value, str):
                    return False

    return True
