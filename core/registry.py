import json
from pathlib import Path
from typing import Dict

from core.context import CreatorContext
from shared.logging.logger import get_logger

log = get_logger("core.registry")

CREATORS_FILE = Path("shared/config/creators.json")


class CreatorRegistry:
    def load(self) -> Dict[str, CreatorContext]:
        raw = json.loads(CREATORS_FILE.read_text(encoding="utf-8"))

        creators: Dict[str, CreatorContext] = {}

        for entry in raw.get("creators", []):
            if not entry.get("enabled"):
                continue

            ctx = CreatorContext(
                creator_id=entry["creator_id"],
                display_name=entry.get("display_name", entry["creator_id"]),
                platforms=entry.get("platforms", {}),
                limits=entry.get("limits", {})
            )

            creators[ctx.creator_id] = ctx
            log.info(f"Loaded creator: {ctx.creator_id}")

        if not creators:
            log.warning("No enabled creators found")

        return creators
