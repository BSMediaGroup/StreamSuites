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
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        creators = raw.get("creators", [])

        out: Dict[str, CreatorContext] = {}

        for c in creators:
            if not c.get("enabled", True):
                continue

            creator_id = c.get("creator_id")
            if not creator_id:
                continue

            ctx = CreatorContext(
                creator_id=creator_id,
                display_name=c.get("display_name", creator_id),
                platforms=c.get("platforms", {}),
                limits=c.get("limits", {}),

                rumble_channel_url=c.get("rumble_channel_url"),
                rumble_manual_watch_url=c.get("rumble_manual_watch_url"),
                rumble_livestream_api_env_key=c.get("rumble_livestream_api_env_key"),

                rumble_chat_channel_id=c.get("rumble_chat_channel_id"),
                rumble_dom_chat_enabled=c.get("rumble_dom_chat_enabled", True),
            )

            out[creator_id] = ctx
            log.info(f"Loaded creator: {creator_id}")

        return out
