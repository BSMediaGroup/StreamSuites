import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.config_loader import ConfigLoader
from core.context import CreatorContext
from core.ratelimits import merge_ratelimits
from shared.logging.logger import get_logger

log = get_logger("core.registry")

CREATORS_PATH = Path("shared/config/creators.json")
TIERS_PATH = Path("shared/config/tiers.json")
RATELIMITS_SCHEMA_PATH = Path("shared/config/ratelimits.schema.json")


class CreatorRegistry:
    def __init__(
        self,
        creators_path: Path = CREATORS_PATH,
        tiers_path: Path = TIERS_PATH,
        config_loader: Optional[ConfigLoader] = None,
    ):
        self.creators_path = creators_path
        self.tiers_path = tiers_path
        self._config_loader = config_loader or ConfigLoader()

        self._tiers = self._load_tiers()
        self._ratelimits_schema = self._load_ratelimits_schema()

    # ------------------------------------------------------------------
    # RATE LIMIT SCHEMA (INTENT, NOT ENFORCEMENT)
    # ------------------------------------------------------------------

    def _load_ratelimits_schema(self) -> Dict[str, Any]:
        if not RATELIMITS_SCHEMA_PATH.exists():
            log.warning("Rate limits schema not found — proceeding without it")
            return {}

        try:
            return json.loads(
                RATELIMITS_SCHEMA_PATH.read_text(encoding="utf-8")
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load ratelimits schema: {e}"
            ) from e

    # ------------------------------------------------------------------
    # TIERS (POLICY LOADING)
    # ------------------------------------------------------------------

    def _load_tiers(self) -> Dict[str, Any]:
        if not self.tiers_path.exists():
            raise RuntimeError(f"Tier policy not found: {self.tiers_path}")

        raw = json.loads(self.tiers_path.read_text(encoding="utf-8"))

        tiers = raw.get("tiers")
        if not isinstance(tiers, dict) or not tiers:
            raise RuntimeError("Tier policy invalid or empty")

        return tiers

    def _resolve_tier(self, tier_name: str) -> Dict[str, Any]:
        tier = self._tiers.get(tier_name)
        if not tier:
            raise RuntimeError(f"Unknown tier: {tier_name}")

        features = tier.get("features")
        if not isinstance(features, dict):
            raise RuntimeError(f"Tier '{tier_name}' missing features block")

        return features

    # ------------------------------------------------------------------
    # FEATURE → RUNTIME LIMIT COMPILATION (AUTHORITATIVE)
    # ------------------------------------------------------------------

    def _compile_runtime_limits(self, features: Dict[str, Any]) -> Dict[str, Any]:
        limits: Dict[str, Any] = {}

        # -----------------------------
        # CLIPS
        # -----------------------------
        clips = features.get("clips", {})
        if clips.get("enabled"):
            limits["max_concurrent_clip_jobs"] = clips.get("max_concurrent_jobs", 1)
            limits["clip_max_duration_seconds"] = clips.get("max_duration_seconds", 30)
            limits["clip_min_cooldown_seconds"] = clips.get("min_cooldown_seconds", 120)

        # -----------------------------
        # TRIGGERS
        # -----------------------------
        triggers = features.get("triggers", {})
        if triggers.get("enabled"):
            limits["max_triggers"] = triggers.get("max_triggers", 10)
            limits["trigger_min_cooldown_seconds"] = triggers.get(
                "min_cooldown_seconds", 2.0
            )

        # -----------------------------
        # POLLS
        # -----------------------------
        polls = features.get("polls", {})
        if polls.get("enabled"):
            limits["max_active_polls"] = polls.get("max_active_polls", 1)
            limits["max_poll_options"] = polls.get("max_options", 4)

        # -----------------------------
        # BACKUPS
        # -----------------------------
        backups = features.get("backups", {})
        limits["backup_manual_export"] = bool(backups.get("manual_export", False))
        limits["backup_automated"] = bool(backups.get("automated_backups", False))
        limits["backup_retention_days"] = backups.get("retention_days", 0)
        limits["backup_interval_hours"] = backups.get("backup_interval_hours")

        return limits

    # ------------------------------------------------------------------
    # CREATORS
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_platforms(raw: Any, known_platforms: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        platforms: Dict[str, bool] = {}

        if isinstance(raw, dict):
            for name, cfg in raw.items():
                if isinstance(cfg, dict):
                    platforms[name] = bool(cfg.get("enabled", cfg.get("active", False) or cfg.get("value", False)))
                else:
                    platforms[name] = bool(cfg)
        elif isinstance(raw, list):
            for cfg in raw:
                if isinstance(cfg, str):
                    platforms[cfg] = True
                elif isinstance(cfg, dict):
                    name = cfg.get("name") or cfg.get("platform")
                    if name:
                        platforms[name] = bool(cfg.get("enabled", True))

        if known_platforms:
            for name in known_platforms.keys():
                platforms.setdefault(name, False)

        return platforms

    def load(
        self,
        creators_data: Optional[List[Dict[str, Any]]] = None,
        platform_defaults: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, CreatorContext]:
        if creators_data is not None:
            raw_creators = creators_data
        elif self.creators_path != CREATORS_PATH:
            try:
                raw = json.loads(self.creators_path.read_text(encoding="utf-8"))
                raw_creators = raw.get("creators", [])
            except Exception as e:
                log.warning(f"Failed to load creators from {self.creators_path}: {e}")
                raw_creators = []
        else:
            raw_creators = self._config_loader.load_creators_config()

        out: Dict[str, CreatorContext] = {}

        for c in raw_creators:
            creator_id = c.get("creator_id")
            if not creator_id:
                log.warning("Skipping creator without creator_id in creators.json")
                continue

            if not c.get("enabled", True):
                log.info(f"[{creator_id}] Creator disabled — excluded from runtime")
                continue

            tier_name = c.get("tier", "open")
            try:
                features = self._resolve_tier(tier_name)
            except Exception as e:
                log.warning(f"[{creator_id}] Invalid tier '{tier_name}': {e}")
                continue

            # --------------------------------------------------
            # Tier-derived runtime limits
            # --------------------------------------------------

            runtime_limits = self._compile_runtime_limits(features)

            # --------------------------------------------------
            # Rate limit schema merge (GLOBAL → PLATFORM → CREATOR)
            # --------------------------------------------------

            platform_name = None
            platforms = self._normalize_platforms(c.get("platforms", {}), platform_defaults)

            if platforms.get("youtube"):
                platform_name = "youtube"
            elif platforms.get("twitch"):
                platform_name = "twitch"
            elif platforms.get("rumble"):
                platform_name = "rumble"

            schema_limits = merge_ratelimits(
                schema=self._ratelimits_schema,
                creator_id=creator_id,
                platform=platform_name,
                creator_limits=c.get("limits"),
            )

            # Schema overrides tier-derived limits
            runtime_limits.update(schema_limits)

            # --------------------------------------------------
            # Creator context (RUNTIME OBJECT)
            # --------------------------------------------------
            try:
                ctx = CreatorContext(
                    creator_id=creator_id,
                    display_name=c.get("display_name", creator_id),
                    platforms=platforms,
                    limits=runtime_limits,

                    rumble_channel_url=c.get("rumble_channel_url"),
                    rumble_manual_watch_url=c.get("rumble_manual_watch_url"),

                    rumble_livestream_api_env_key=c.get("rumble_livestream_api_env_key"),

                    rumble_chat_channel_id=c.get("rumble_chat_channel_id"),
                    rumble_dom_chat_enabled=c.get("rumble_dom_chat_enabled", True),
                )
            except Exception as e:
                log.warning(f"[{creator_id}] Creator skipped due to invalid config: {e}")
                continue

            # Attach features explicitly (read-only intent)
            ctx.features = features  # type: ignore[attr-defined]

            out[creator_id] = ctx

            log.info(
                f"Loaded creator: {creator_id} "
                f"(tier={tier_name}, limits={runtime_limits})"
            )

        return out
