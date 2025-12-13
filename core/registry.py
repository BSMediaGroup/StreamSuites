import json
from pathlib import Path
from typing import Dict

from core.context import CreatorContext
from shared.logging.logger import get_logger

log = get_logger("core.registry")

CREATORS_PATH = Path("shared/config/creators.json")


class CreatorRegistry:
    def __init__(self, path: Path = CREATORS_PATH):
        self.path = path

    def load(self) -> Dict[str, CreatorContext]:
        """
        Load creators from shared/config/creators.json and return a map:
        { creator_id: CreatorContext }
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Creators config not found: {self.path}")

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        creators = raw.get("creators", [])

        out: Dict[str, CreatorContext] = {}

        for c in creators:
            if not c.get("enabled", True):
                continue

            creator_id = c.get("creator_id")
            if not creator_id:
                log.error("Creator entry missing creator_id; skipping")
                continue

            ctx = CreatorContext(
                creator_id=creator_id,
                display_name=c.get("display_name", creator_id),
                platforms=c.get("platforms", {}),
                limits=c.get("limits", {}),

                # Platform-specific config (additive, non-breaking)
                rumble_channel_url=c.get("rumble_channel_url"),
                rumble_watch_url=c.get("rumble_watch_url"),
            )

            out[creator_id] = ctx
            log.info(f"Loaded creator: {creator_id}")

        return out
