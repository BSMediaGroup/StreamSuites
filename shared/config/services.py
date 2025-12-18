"""
Services configuration loader.

This module provides access to deployment-level service toggles
(e.g. Discord control-plane enablement).

Design rules:
- Import-safe (no side effects)
- JSON-only configuration
- Defensive defaults
- Runtime is authoritative; missing keys disable features
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from shared.logging.logger import get_logger

log = get_logger("shared.config.services")


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent / "services.json"


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def get_services_config() -> Dict[str, Any]:
    """
    Load and return the services configuration.

    Expected shape (minimal):
    {
        "discord": {
            "enabled": true
        }
    }

    Missing files or keys are treated as disabled services.
    """

    data: Dict[str, Any] = {}

    try:
        if _CONFIG_PATH.exists():
            with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    data = raw
                else:
                    log.warning(
                        "services.json root is not an object; ignoring"
                    )
        else:
            log.debug("services.json not found; using defaults")
    except Exception as e:
        log.warning(f"Failed to load services.json; using defaults: {e}")

    # --------------------------------------------------------
    # Defensive defaults (authoritative)
    # --------------------------------------------------------

    services: Dict[str, Any] = {}

    discord_cfg = data.get("discord", {})
    services["discord"] = {
        "enabled": bool(discord_cfg.get("enabled", False))
    }

    return services
