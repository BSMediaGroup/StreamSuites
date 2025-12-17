import json
from pathlib import Path
from typing import Dict

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
    # TIERS
    # ------------------------------------------------------------------

    def _load_tiers(self) -> dict:
        if not self.tiers_path.exists():
            raise RuntimeError(
                f"Tier policy not found: {self.tiers_path}"
            )

        raw = json.loads(self.tiers_path.read_text(encoding="utf-8"))

        tiers = raw.get("tiers")
        if not isinstance(tiers, dict) or not tiers:
            raise RuntimeError("Tier policy invalid or empty")

        return tiers

    def _resolve_tier_limits(self, tier_name: str) -> dict:
        tier = self._tiers.get(tier_name)
        if not tier:
            raise RuntimeError(f"Unknown tier: {tier_name}")

        features = tier.get("features")
        if not isinstance(features, dict):
            raise RuntimeError(f"Tier '{tier_name}' missing features block")

        return features

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

            # ----------------------------------------------------------
            # TIER RESOLUTION (AUTHORITATIVE)
            # ----------------------------------------------------------

            tier_name = c.get("tier", "open")
            limits = self._resolve_tier_limits(tier_name)

            # ----------------------------------------------------------
            # CONTEXT
            # ----------------------------------------------------------

            ctx = CreatorContext(
                creator_id=creator_id,
                display_name=c.get("display_name", creator_id),
                platforms=c.get("platforms", {}),
                limits=limits,

                rumble_channel_url=c.get("rumble_channel_url"),
                rumble_manual_watch_url=c.get("rumble_manual_watch_url"),
                rumble_livestream_api_env_key=c.get("rumble_livestream_api_env_key"),

                rumble_chat_channel_id=c.get("rumble_chat_channel_id"),
                rumble_dom_chat_enabled=c.get("rumble_dom_chat_enabled", True),
            )

            out[creator_id] = ctx
            log.info(
                f"Loaded creator: {creator_id} (tier={tier_name})"
            )

        return out
