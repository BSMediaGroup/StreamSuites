"""
Services configuration loader.

This module provides access to deployment-level service toggles
(e.g. Discord control-plane enablement).

Design rules:
- Import-safe (no side effects)
- JSON-only configuration
- Runtime is authoritative
- Missing services default to disabled
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

    Expected shape:
    {
        "youtube": { "enabled": true },
        "twitch":  { "enabled": false },
        "rumble":  { "enabled": false },
        "twitter": { "enabled": true },
        "discord": { "enabled": false }
    }

    Rules:
    - Missing services default to enabled=False
    - Unknown services are preserved
    - Invalid shapes are ignored per-key, not globally
    """

    raw: Dict[str, Any] = {}

    try:
        if _CONFIG_PATH.exists():
            with _CONFIG_PATH.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    raw = loaded
                else:
                    log.warning(
                        "services.json root is not an object; ignoring file"
                    )
        else:
            log.debug("services.json not found; all services disabled")
    except Exception as e:
        log.warning(f"Failed to load services.json; all services disabled: {e}")

    services: Dict[str, Any] = {}

    for service_name, cfg in raw.items():
        if isinstance(cfg, dict):
            services[service_name] = {
                "enabled": bool(cfg.get("enabled", False))
            }
        else:
            log.warning(
                f"Service '{service_name}' config is not an object; disabling"
            )
            services[service_name] = {
                "enabled": False
            }

    return services
