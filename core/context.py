from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class CreatorContext:
    creator_id: str
    display_name: str
    platforms: Dict[str, bool]
    limits: Dict[str, Any]

    # Platform-specific config (additive)
    rumble_channel_url: Optional[str] = None
    rumble_watch_url: Optional[str] = None

    def platform_enabled(self, name: str) -> bool:
        return bool(self.platforms.get(name, False))
