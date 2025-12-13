from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class CreatorContext:
    creator_id: str
    display_name: str
    platforms: Dict[str, bool]
    limits: Dict[str, Any]

    # -------------------------------------------------
    # RUMBLE CONFIG (AUTHORITATIVE + CHAT)
    # -------------------------------------------------
    rumble_channel_url: Optional[str] = None
    rumble_watch_url: Optional[str] = None

    # REQUIRED for REST chat posting
    rumble_chat_channel_id: Optional[str] = None

    def platform_enabled(self, name: str) -> bool:
        return bool(self.platforms.get(name, False))
