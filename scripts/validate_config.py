"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.1-alpha (Build 2025.02)
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


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

def main() -> int:
    ok = True

    if not validate_services_config():
        ok = False

    if not ok:
        print("Configuration validation failed.", file=sys.stderr)
        return 1

    print("Configuration validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
