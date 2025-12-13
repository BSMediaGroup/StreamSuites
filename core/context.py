from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CreatorContext:
    creator_id: str
    display_name: str
    platforms: Dict[str, bool]
    limits: Dict[str, Any]

    def platform_enabled(self, name: str) -> bool:
        return bool(self.platforms.get(name, False))
