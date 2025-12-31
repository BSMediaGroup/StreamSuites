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
    PLATFORM_OVERRIDES_PATH = Path("shared/config/platform_overrides.json")
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

    @staticmethod
    def _normalize_platform_override(entry: Any) -> Optional[tuple[str, bool]]:
        if isinstance(entry, dict):
            name = entry.get("platform_id") or entry.get("platform") or entry.get("name")
            if isinstance(name, str) and "enabled" in entry:
                return name, bool(entry.get("enabled"))
        elif isinstance(entry, (list, tuple)):
            return None
        return None

    def _load_platform_overrides(self) -> Dict[str, bool]:
        raw = self._load_json(self.PLATFORM_OVERRIDES_PATH, "platform_overrides")
        overrides: Dict[str, bool] = {}

        if not raw:
            return overrides

        entries = None
        if isinstance(raw, dict):
            if "platforms" in raw:
                entries = raw.get("platforms")
            else:
                entries = raw
        elif isinstance(raw, list):
            entries = raw

        if isinstance(entries, dict):
            for name, value in entries.items():
                if isinstance(value, dict):
                    enabled_flag = value.get("enabled")
                    if isinstance(enabled_flag, bool):
                        overrides[str(name)] = enabled_flag
                    else:
                        log.warning(
                            f"platform_overrides entry for '{name}' missing bool enabled; skipping"
                        )
                elif isinstance(value, bool):
                    overrides[str(name)] = value
                else:
                    log.warning(
                        f"platform_overrides entry for '{name}' must be bool or object; skipping"
                    )
        elif isinstance(entries, list):
            for entry in entries:
                normalized = self._normalize_platform_override(entry)
                if normalized:
                    name, enabled_flag = normalized
                    overrides[name] = enabled_flag
                else:
                    log.warning("Skipping invalid platform override entry")
        else:
            log.warning(
                "platform_overrides.json has invalid shape (expected object or array); ignoring"
            )

        return overrides

    def _apply_platform_overrides(
        self, config: Dict[str, Dict[str, Any]], overrides: Dict[str, bool]
    ) -> Dict[str, Dict[str, Any]]:
        if not overrides:
            return config

        updated = dict(config)
        for name, enabled_flag in overrides.items():
            existing = updated.get(name, {}) if isinstance(updated.get(name), dict) else {}
            state = normalize_platform_state(
                name, existing.get("state"), enabled=bool(enabled_flag)
            )
            telemetry_enabled = bool(existing.get("telemetry_enabled", enabled_flag))
            paused_reason = existing.get("paused_reason")

            if state == PlatformState.PAUSED and not paused_reason:
                paused_reason = "Platform ingestion paused"

            updated[name] = {
                "enabled": state != PlatformState.DISABLED,
                "telemetry_enabled": telemetry_enabled if state != PlatformState.DISABLED else False,
                "state": state.value,
                "paused_reason": paused_reason,
            }

        return apply_default_platform_states(updated)

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

        overrides = self._load_platform_overrides()
        if overrides:
            log.info(
                f"Applying platform overrides for {sorted(overrides.keys())} (restart required)"
            )
            try:
                return self._apply_platform_overrides(platforms_cfg, overrides)
            except Exception as e:  # pragma: no cover - defensive
                log.warning(f"Failed to apply platform overrides; using base config: {e}")

        return platforms_cfg

