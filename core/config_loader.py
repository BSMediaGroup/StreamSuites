"""
Configuration loader with dashboard compatibility.

This module centralizes ingestion of dashboard-generated config files and
applies lightweight schema validation. Failures are treated as warnings so the
runtime can continue booting with best-effort defaults.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.config.services import get_services_config
from shared.platforms.state import (
    PlatformState,
    apply_default_platform_states,
    normalize_platform_state,
)

log = get_logger("core.config_loader")


try:  # Optional dependency for JSON Schema validation
    from jsonschema import Draft7Validator
except Exception:  # pragma: no cover - optional dependency guard
    Draft7Validator = None  # type: ignore


class ConfigLoader:
    """
    Loads and validates dashboard-provided configuration documents.

    Files:
      - shared/config/creators.json
      - shared/config/platforms.json (authoritative platform toggles)

    Fallback:
      - shared/config/services.json (legacy platform toggles)

    Validation:
      - If schemas are present under ./schemas/, validate and log warnings on
        failure without aborting runtime startup.
    """

    CREATORS_PATH = Path("shared/config/creators.json")
    PLATFORMS_PATH = Path("shared/config/platforms.json")
    SCHEMA_DIR = Path("schemas")

    def __init__(self) -> None:
        self._creators_schema_path = self.SCHEMA_DIR / "creators.schema.json"
        self._platforms_schema_path = self.SCHEMA_DIR / "platforms.schema.json"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_json(self, path: Path, name: str) -> Dict[str, Any]:
        if not path.exists():
            log.warning(f"{name} config not found at {path}; using defaults")
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                log.warning(f"{name} config root is not an object; ignoring")
        except Exception as e:  # pragma: no cover - defensive path
            log.warning(f"Failed to load {name} config ({e}); using defaults")

        return {}

    def _validate(self, payload: Dict[str, Any], schema_path: Path, name: str) -> None:
        if not Draft7Validator:
            log.debug("jsonschema not installed; skipping validation")
            return

        if not schema_path.exists():
            log.debug(f"Schema for {name} not found at {schema_path}; skipping")
            return

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - defensive
            log.warning(f"Failed to load {name} schema ({e}); skipping validation")
            return

        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))

        if errors:
            for err in errors:
                loc = "/".join(str(p) for p in err.path)
                log.warning(f"{name} config validation warning at '{loc}': {err.message}")

    @staticmethod
    def _normalize_platform_entry(entry: Any) -> Optional[tuple[str, Dict[str, Any]]]:
        if not isinstance(entry, dict):
            return None

        name = entry.get("name") or entry.get("platform")
        if not name or not isinstance(name, str):
            return None

        enabled_flag = bool(entry.get("enabled", False))
        state = normalize_platform_state(name, entry.get("state"), enabled=enabled_flag)
        enabled = state != PlatformState.DISABLED
        telemetry_enabled = bool(entry.get("telemetry_enabled", enabled_flag)) if enabled else False
        paused_reason = entry.get("paused_reason")

        return name, {
            "enabled": enabled,
            "telemetry_enabled": telemetry_enabled,
            "state": state.value,
            "paused_reason": paused_reason,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_creators_config(self) -> List[Dict[str, Any]]:
        """
        Load creators.json (dashboard export) with schema validation.

        Returns a list of creator objects (raw) while preserving disabled
        creators for export. Invalid entries are skipped with warnings.
        """

        data = self._load_json(self.CREATORS_PATH, "creators")
        self._validate(data, self._creators_schema_path, "creators")

        creators = data.get("creators")
        if not isinstance(creators, list):
            log.warning("creators.json missing 'creators' array; using empty list")
            return []

        sanitized: List[Dict[str, Any]] = []
        for entry in creators:
            if isinstance(entry, dict) and entry.get("creator_id"):
                sanitized.append(entry)
            else:
                log.warning("Skipping invalid creator entry (expected object with creator_id)")

        return sanitized

    def load_platforms_config(self) -> Dict[str, Dict[str, bool]]:
        """
        Load platforms.json (dashboard export) or fall back to services.json.

        Returns a normalized mapping: platform -> {enabled, telemetry_enabled}.
        """

        data = self._load_json(self.PLATFORMS_PATH, "platforms")
        if data:
            self._validate(data, self._platforms_schema_path, "platforms")

        platforms_cfg: Dict[str, Dict[str, bool]] = {}
        entries = data.get("platforms") if isinstance(data, dict) else None

        if isinstance(entries, list):
            for entry in entries:
                normalized = self._normalize_platform_entry(entry)
                if normalized:
                    name, cfg = normalized
                    platforms_cfg[name] = cfg
                else:
                    log.warning("Skipping invalid platform entry in platforms.json")

        if not platforms_cfg:
            log.info("platforms.json missing or empty; falling back to services.json")
            for name, cfg in get_services_config().items():
                enabled = bool(cfg.get("enabled", False))
                telemetry_enabled = bool(cfg.get("telemetry_enabled", enabled))
                state = normalize_platform_state(name, cfg.get("state"), enabled=enabled)
                platforms_cfg[name] = {
                    "enabled": state != PlatformState.DISABLED,
                    "telemetry_enabled": telemetry_enabled if state != PlatformState.DISABLED else False,
                    "state": state.value,
                    "paused_reason": cfg.get("paused_reason"),
                }

        apply_default_platform_states(platforms_cfg)

        return platforms_cfg

