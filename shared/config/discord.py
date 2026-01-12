"""
Discord configuration loader for per-guild settings.

Design rules:
- Import-safe (no side effects)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from shared.logging.logger import get_logger

log = get_logger("shared.config.discord")

_CONFIG_PATH = Path(__file__).parent / "discord.json"
_CREATORS_PATH = Path(__file__).parent / "creators.json"

CLIP_NOTIFICATION_LABELS: Dict[str, str] = {
    "rumble": "Rumble clips",
    "youtube": "YouTube clips",
    "kick": "Kick clips",
    "pilled": "Pilled clips",
    "twitch": "Twitch clips",
}
CLIP_NOTIFICATION_KEYS = tuple(CLIP_NOTIFICATION_LABELS.keys())

NOTIFICATION_KIND_LABELS: Dict[str, str] = {
    "general": "General",
    **{f"clips:{key}": label for key, label in CLIP_NOTIFICATION_LABELS.items()},
}
NOTIFICATION_KIND_KEYS = tuple(NOTIFICATION_KIND_LABELS.keys())

LEGACY_NOTIFICATION_MAP = {
    "notifications_general": "general",
    "notifications_rumble_clips": "clips:rumble",
    "notifications_youtube_clips": "clips:youtube",
    "notifications_kick_clips": "clips:kick",
    "notifications_pilled_clips": "clips:pilled",
    "notifications_twitch_clips": "clips:twitch",
}

LEGACY_NOTIFICATION_KEY_MAP = {
    "rumble_clips": "clips:rumble",
    "youtube_clips": "clips:youtube",
    "kick_clips": "clips:kick",
    "pilled_clips": "clips:pilled",
    "twitch_clips": "clips:twitch",
}

_DEFAULT_LOGGING_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "channel_id": None,
}

_DEFAULT_NOTIFICATIONS: Dict[str, Any] = {
    "enabled": False,
    "general": {"channel_id": None},
    "clips": {
        key: {"channel_id": None}
        for key in CLIP_NOTIFICATION_KEYS
    },
}

_DEFAULT_GUILD_CONFIG: Dict[str, Any] = {
    "logging": dict(_DEFAULT_LOGGING_CONFIG),
    "notifications": copy.deepcopy(_DEFAULT_NOTIFICATIONS),
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


def _normalize_admin_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw and raw.isdigit():
            return raw
    return None


def _normalize_admin_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for entry in raw:
        admin_id = _normalize_admin_id(entry)
        if admin_id:
            normalized.append(admin_id)
    return normalized


def _set_notification_channel(data: Dict[str, Any], kind: str, value: Any) -> None:
    channel_id = _normalize_channel_id(value)
    if kind == "general":
        data["notifications"]["general"]["channel_id"] = channel_id
        return
    if kind.startswith("clips:"):
        clip_key = kind.split(":", 1)[1]
        if clip_key in data["notifications"]["clips"]:
            data["notifications"]["clips"][clip_key]["channel_id"] = channel_id


def _normalize_guild_config(raw: Any) -> Dict[str, Any]:
    data = {
        "logging": dict(_DEFAULT_LOGGING_CONFIG),
        "notifications": copy.deepcopy(_DEFAULT_NOTIFICATIONS),
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
        notifications_enabled = notifications_raw.get("enabled")
        if isinstance(notifications_enabled, bool):
            data["notifications"]["enabled"] = notifications_enabled

        general_raw = notifications_raw.get("general")
        if isinstance(general_raw, dict):
            _set_notification_channel(
                data,
                "general",
                general_raw.get("channel_id"),
            )
        elif general_raw is not None:
            _set_notification_channel(data, "general", general_raw)

        clips_raw = notifications_raw.get("clips")
        if isinstance(clips_raw, dict):
            for clip_key in CLIP_NOTIFICATION_KEYS:
                if clip_key not in clips_raw:
                    continue
                entry = clips_raw.get(clip_key)
                if isinstance(entry, dict):
                    _set_notification_channel(
                        data,
                        f"clips:{clip_key}",
                        entry.get("channel_id"),
                    )
                else:
                    _set_notification_channel(data, f"clips:{clip_key}", entry)

        for legacy_key, kind in LEGACY_NOTIFICATION_KEY_MAP.items():
            if legacy_key in notifications_raw:
                _set_notification_channel(data, kind, notifications_raw.get(legacy_key))

    for legacy_key, notification_key in LEGACY_NOTIFICATION_MAP.items():
        if legacy_key in raw:
            _set_notification_channel(data, notification_key, raw.get(legacy_key))

    return data


def load_discord_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = path or _CONFIG_PATH

    if not config_path.exists():
        return {"discord": {"admins": [], "guilds": {}}}

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Failed to load discord config ({exc}); using defaults")
        return {"discord": {"admins": [], "guilds": {}}}

    if not isinstance(data, dict):
        return {"discord": {"admins": [], "guilds": {}}}

    discord_root = data.get("discord", {})
    if isinstance(discord_root, dict):
        admins_raw = discord_root.get("admins", [])
        guilds_raw = discord_root.get("guilds", {})
    else:
        admins_raw = data.get("admins", [])
        guilds_raw = data.get("guilds", {})
    guilds: Dict[str, Any] = {}
    admins = _normalize_admin_list(admins_raw)

    if isinstance(guilds_raw, dict):
        for guild_id, entry in guilds_raw.items():
            if not isinstance(entry, dict):
                continue
            guilds[str(guild_id)] = _normalize_guild_config(entry)

    return {"discord": {"admins": admins, "guilds": guilds}}


def save_discord_config(config: Dict[str, Any], path: Optional[Path] = None) -> None:
    config_path = path or _CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    discord_root = config.get("discord", {}) if isinstance(config, dict) else {}
    if isinstance(discord_root, dict):
        admins = discord_root.get("admins", [])
        guilds = discord_root.get("guilds", {})
    else:
        admins = config.get("admins", []) if isinstance(config, dict) else []
        guilds = config.get("guilds", {}) if isinstance(config, dict) else {}

    payload = {
        "discord": {
            "admins": _normalize_admin_list(admins),
            "guilds": guilds if isinstance(guilds, dict) else {},
        }
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
    discord_root.setdefault("admins", [])
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
            notifications_enabled = value.get("enabled")
            if isinstance(notifications_enabled, bool):
                current["notifications"]["enabled"] = notifications_enabled

            if "general" in value:
                general_value = value.get("general")
                if isinstance(general_value, dict):
                    _set_notification_channel(
                        current,
                        "general",
                        general_value.get("channel_id"),
                    )
                else:
                    _set_notification_channel(current, "general", general_value)

            clips_value = value.get("clips")
            if isinstance(clips_value, dict):
                for clip_key, clip_entry in clips_value.items():
                    if clip_key not in CLIP_NOTIFICATION_KEYS:
                        continue
                    if isinstance(clip_entry, dict):
                        _set_notification_channel(
                            current,
                            f"clips:{clip_key}",
                            clip_entry.get("channel_id"),
                        )
                    else:
                        _set_notification_channel(current, f"clips:{clip_key}", clip_entry)

            for legacy_key, kind in LEGACY_NOTIFICATION_KEY_MAP.items():
                if legacy_key in value:
                    _set_notification_channel(current, kind, value.get(legacy_key))
            continue

        if key == "logging_enabled":
            if isinstance(value, bool):
                current["logging"]["enabled"] = value
            continue

        if key == "logging_channel_id":
            current["logging"]["channel_id"] = _normalize_channel_id(value)
            continue

        if key in LEGACY_NOTIFICATION_MAP:
            _set_notification_channel(current, LEGACY_NOTIFICATION_MAP[key], value)

    guilds[str(guild_id)] = current
    save_discord_config(config, path)
    return current


def default_guild_config() -> Dict[str, Any]:
    return _normalize_guild_config({})


def notification_kind_keys() -> tuple[str, ...]:
    return NOTIFICATION_KIND_KEYS


def notification_kind_label(kind: str) -> str:
    return NOTIFICATION_KIND_LABELS.get(kind, kind.replace("_", " ").title())


def clip_notification_keys() -> tuple[str, ...]:
    return CLIP_NOTIFICATION_KEYS


def clip_notification_label(key: str) -> str:
    return CLIP_NOTIFICATION_LABELS.get(key, key.replace("_", " ").title())


def get_notification_channel_id(
    guild_id: int,
    kind: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
) -> Optional[int]:
    config = config or load_discord_config(path)
    entry = get_guild_config(guild_id, config=config, path=path)
    notifications = entry.get("notifications", {})
    if not isinstance(notifications, dict):
        return None

    if not notifications.get("enabled", False):
        return None

    if kind == "general":
        general = notifications.get("general", {})
        if isinstance(general, dict):
            return parse_channel_id(general.get("channel_id"))
        return None

    if kind.startswith("clips:"):
        clip_key = kind.split(":", 1)[1]
        clips = notifications.get("clips", {})
        if isinstance(clips, dict):
            clip_entry = clips.get(clip_key, {})
            if isinstance(clip_entry, dict):
                return parse_channel_id(clip_entry.get("channel_id"))
        return None

    return None


def build_guild_exports(
    *,
    config: Optional[Dict[str, Any]] = None,
    bot_guild_ids: Optional[Iterable[int]] = None,
    user_id: Optional[str] = None,
    path: Optional[Path] = None,
) -> list[Dict[str, Any]]:
    config = config or load_discord_config(path)
    discord_root = config.get("discord", {}) if isinstance(config, dict) else {}
    guilds_raw = discord_root.get("guilds", {}) if isinstance(discord_root, dict) else {}
    guild_ids: set[int] = set()

    if isinstance(guilds_raw, dict):
        for guild_id in guilds_raw.keys():
            try:
                guild_ids.add(int(guild_id))
            except (TypeError, ValueError):
                continue

    bot_guild_id_set: set[int] = set()
    if bot_guild_ids:
        for guild_id in bot_guild_ids:
            try:
                bot_guild_id_set.add(int(guild_id))
            except (TypeError, ValueError):
                continue
        guild_ids.update(bot_guild_id_set)

    exports: list[Dict[str, Any]] = []
    for guild_id in sorted(guild_ids):
        entry = get_guild_config(guild_id, config=config, path=path)
        export = {
            "guild_id": guild_id,
            "bot_present": guild_id in bot_guild_id_set,
            "logging": entry.get("logging", {}),
            "notifications": entry.get("notifications", {}),
        }
        if user_id is not None:
            export["authorized_admin_override"] = (
                is_discord_admin(user_id, config=config, path=path)
                and export["bot_present"]
            )
        exports.append(export)
    return exports


def parse_channel_id(value: Any) -> Optional[int]:
    normalized = _normalize_channel_id(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def get_discord_admins(
    config: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
) -> tuple[str, ...]:
    config = config or load_discord_config(path)
    discord_root = config.get("discord", {}) if isinstance(config, dict) else {}
    if isinstance(discord_root, dict):
        admins_raw = discord_root.get("admins", [])
    else:
        admins_raw = config.get("admins", []) if isinstance(config, dict) else []
    return tuple(_normalize_admin_list(admins_raw))


def _load_creator_admins(path: Optional[Path] = None) -> list[str]:
    creators_path = path or _CREATORS_PATH
    if not creators_path.exists():
        return []
    try:
        payload = json.loads(creators_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Failed to load creators config ({exc}); ignoring admin overrides")
        return []

    if not isinstance(payload, dict):
        return []

    admins: list[str] = []
    admins.extend(_normalize_admin_list(payload.get("discord_admins", [])))
    creators = payload.get("creators", [])
    if isinstance(creators, list):
        for entry in creators:
            if not isinstance(entry, dict):
                continue
            if not entry.get("is_admin"):
                continue
            admin_id = _normalize_admin_id(entry.get("discord_user_id"))
            if admin_id:
                admins.append(admin_id)
    return admins


def is_discord_admin(
    user_id: str | int,
    config: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
    creators_path: Optional[Path] = None,
) -> bool:
    normalized = _normalize_admin_id(user_id)
    if not normalized:
        return False
    admins = set(get_discord_admins(config=config, path=path))
    admins.update(_load_creator_admins(creators_path))
    return normalized in admins


def validate_discord_config(config: Dict[str, Any]) -> bool:
    if not isinstance(config, dict):
        return False

    discord_root = config.get("discord", {})
    if discord_root is None:
        return True
    if not isinstance(discord_root, dict):
        return False

    admins = discord_root.get("admins", [])
    if admins is not None:
        if not isinstance(admins, list):
            return False
        for entry in admins:
            if not isinstance(entry, str):
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
            enabled = notifications_raw.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                return False
            general = notifications_raw.get("general")
            if general is not None:
                if not isinstance(general, dict):
                    return False
                general_channel = general.get("channel_id")
                if general_channel is not None and not isinstance(general_channel, str):
                    return False
            clips = notifications_raw.get("clips")
            if clips is not None:
                if not isinstance(clips, dict):
                    return False
                for clip_key, clip_entry in clips.items():
                    if clip_entry is None:
                        continue
                    if not isinstance(clip_entry, dict):
                        return False
                    channel_id = clip_entry.get("channel_id")
                    if channel_id is not None and not isinstance(channel_id, str):
                        return False

    return True
