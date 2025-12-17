import json
from pathlib import Path
from typing import Dict, Any

from core.context import CreatorContext
from shared.logging.logger import get_logger

log = get_logger("core.registry")

CREATORS_PATH = Path("shared/config/creators.json")
TIERS_PATH = Path("shared/config/tiers.json")


class CreatorRegistry:
    def __init__(
        self,
        creators_path: Path = CREATORS_PATH,
        tiers_path: Path = TIERS_PATH,
    ):
        self.creators_path = creators_path
        self.tiers_path = tiers_path

        self._tiers = self._load_tiers()

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

    def load(self) -> Dict[str, CreatorContext]:
        raw = json.loads(self.creators_path.read_text(encoding="utf-8"))
        creators = raw.get("creators", [])

        out: Dict[str, CreatorContext] = {}

        for c in creators:
            if not c.get("enabled", True):
                continue

            creator_id = c.get("creator_id")
            if not creator_id:
                continue

            tier_name = c.get("tier", "open")
            features = self._resolve_tier(tier_name)
            runtime_limits = self._compile_runtime_limits(features)

            ctx = CreatorContext(
                creator_id=creator_id,
                display_name=c.get("display_name", creator_id),
                platforms=c.get("platforms", {}),
                limits=runtime_limits,

                rumble_channel_url=c.get("rumble_channel_url"),
                rumble_manual_watch_url=c.get("rumble_manual_watch_url"),
                rumble_livestream_api_env_key=c.get("rumble_livestream_api_env_key"),

                rumble_chat_channel_id=c.get("rumble_chat_channel_id"),
                rumble_dom_chat_enabled=c.get("rumble_dom_chat_enabled", True),
            )

            # Attach features explicitly (read-only intent)
            ctx.features = features  # type: ignore[attr-defined]

            out[creator_id] = ctx

            log.info(
                f"Loaded creator: {creator_id} "
                f"(tier={tier_name}, limits={runtime_limits})"
            )

        return out
