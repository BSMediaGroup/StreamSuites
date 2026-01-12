"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.2-alpha (Build 2025.03)
Owner: Daniel Clancy
 Copyright © 2026 Brainstream Media Group
======================================================================
"""

"""
Configuration validation script.

This script validates JSON configuration files against
minimal runtime expectations.

Design rules:
- No side effects on import
- No runtime startup
- Validation only (no mutation)
- Forward-compatible: unknown fields are ignored
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "shared" / "config"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            raise ValueError("Root JSON value must be an object")
    except Exception as e:
        raise ValueError(f"{path.name}: invalid JSON ({e})") from e


def _error(msg: str):
    print(f"[CONFIG ERROR] {msg}", file=sys.stderr)


# ------------------------------------------------------------
# Validators
# ------------------------------------------------------------

def validate_services_config() -> bool:
    """
    Validate shared/config/services.json.

    Expected (minimal) shape:
    {
        "discord": {
            "enabled": true | false
        }
    }

    Missing keys are allowed.
    Invalid types are rejected.
    """

    path = CONFIG_DIR / "services.json"
    data = _load_json(path)

    discord_cfg = data.get("discord")
    if discord_cfg is None:
        return True

    if not isinstance(discord_cfg, dict):
        _error("services.json: 'discord' must be an object")
        return False

    enabled = discord_cfg.get("enabled")
    if enabled is None:
        return True

    if not isinstance(enabled, bool):
        _error("services.json: 'discord.enabled' must be a boolean")
        return False

    return True


def validate_discord_config() -> bool:
    """
    Validate shared/config/discord.json.

    Expected (authoritative) shape:
    {
        "discord": {
            "guilds": {
                "<guild_id>": {
                    "logging": { "enabled": bool, "channel_id": string | null },
                    "notifications": { "<type>": string | null }
                }
            }
        }
    }

    Legacy root-level "guilds" entries are tolerated for compatibility.
    """

    path = CONFIG_DIR / "discord.json"
    data = _load_json(path)

    discord_root = data.get("discord")
    guilds = None

    if discord_root is not None:
        if not isinstance(discord_root, dict):
            _error("discord.json: 'discord' must be an object")
            return False
        guilds = discord_root.get("guilds")
    else:
        guilds = data.get("guilds")

    if guilds is None:
        return True

    if not isinstance(guilds, dict):
        _error("discord.json: 'guilds' must be an object")
        return False

    for guild_id, entry in guilds.items():
        if not isinstance(entry, dict):
            continue

        logging = entry.get("logging")
        if logging is not None:
            if not isinstance(logging, dict):
                _error(f"discord.json: 'logging' for guild {guild_id} must be an object")
                return False
            enabled = logging.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                _error(f"discord.json: 'logging.enabled' for guild {guild_id} must be a boolean")
                return False
            channel_id = logging.get("channel_id")
            if channel_id is not None and not isinstance(channel_id, (str, int)):
                _error(
                    f"discord.json: 'logging.channel_id' for guild {guild_id} must be a string"
                )
                return False

        notifications = entry.get("notifications")
        if notifications is not None:
            if not isinstance(notifications, dict):
                _error(
                    f"discord.json: 'notifications' for guild {guild_id} must be an object"
                )
                return False
            for value in notifications.values():
                if value is not None and not isinstance(value, (str, int)):
                    _error(
                        f"discord.json: notification values for guild {guild_id} must be strings"
                    )
                    return False

        logging_enabled = entry.get("logging_enabled")
        if logging_enabled is not None and not isinstance(logging_enabled, bool):
            _error(f"discord.json: 'logging_enabled' for guild {guild_id} must be a boolean")
            return False

        logging_channel_id = entry.get("logging_channel_id")
        if logging_channel_id is not None and not isinstance(logging_channel_id, (str, int)):
            _error(
                f"discord.json: 'logging_channel_id' for guild {guild_id} must be a string"
            )
            return False

    return True


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def main() -> int:
    ok = True

    if not validate_services_config():
        ok = False

    if not validate_discord_config():
        ok = False

    if not ok:
        print("Configuration validation failed.", file=sys.stderr)
        return 1

    print("Configuration validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
