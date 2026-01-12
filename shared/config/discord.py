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

_DEFAULT_GUILD_CONFIG: Dict[str, Any] = {
    "logging_enabled": False,
    "logging_channel_id": None,
    "notifications_general": None,
    "notifications_rumble_clips": None,
    "notifications_youtube_clips": None,
    "notifications_kick_clips": None,
    "notifications_pilled_clips": None,
    "notifications_twitch_clips": None,
}


def _normalize_channel_id(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _normalize_guild_config(raw: Any) -> Dict[str, Any]:
    data = dict(_DEFAULT_GUILD_CONFIG)
    if not isinstance(raw, dict):
        return data

    logging_enabled = raw.get("logging_enabled")
    if isinstance(logging_enabled, bool):
        data["logging_enabled"] = logging_enabled

    for key in _DEFAULT_GUILD_CONFIG:
        if key == "logging_enabled":
            continue
        if key in raw:
            data[key] = _normalize_channel_id(raw.get(key))

    return data


def load_discord_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = path or _CONFIG_PATH

    if not config_path.exists():
        return {"guilds": {}}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Failed to load discord config ({exc}); using defaults")
        return {"guilds": {}}

    if not isinstance(data, dict):
        return {"guilds": {}}

    guilds_raw = data.get("guilds", {})
    guilds: Dict[str, Any] = {}

    if isinstance(guilds_raw, dict):
        for guild_id, entry in guilds_raw.items():
            guilds[str(guild_id)] = _normalize_guild_config(entry)

    return {"guilds": guilds}


def save_discord_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    config_path = path or _CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "guilds": config.get("guilds", {}),
    }
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
    guilds = config.setdefault("guilds", {})

    current = _normalize_guild_config(guilds.get(str(guild_id), {}))

    for key, value in updates.items():
        if key not in _DEFAULT_GUILD_CONFIG:
            continue
        if key == "logging_enabled":
            if isinstance(value, bool):
                current[key] = value
        else:
            current[key] = _normalize_channel_id(value)

    guilds[str(guild_id)] = current
    save_discord_config(config, path)
    return current


def default_guild_config() -> Dict[str, Any]:
    return dict(_DEFAULT_GUILD_CONFIG)
