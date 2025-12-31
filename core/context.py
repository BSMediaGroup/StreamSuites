from dataclasses import dataclass
from typing import Dict, Any, Optional
import os

from shared.platforms.state import PlatformState


@dataclass
class CreatorContext:
    # -------------------------------------------------
    # CORE
    # -------------------------------------------------
    creator_id: str
    display_name: str
    platforms: Dict[str, bool]
    limits: Dict[str, Any]
    platform_states: Optional[Dict[str, PlatformState]] = None

    # -------------------------------------------------
    # RUMBLE (MODEL A)
    # -------------------------------------------------
    rumble_channel_url: Optional[str] = None

    # ABSOLUTE AUTHORITY (MODEL A)
    rumble_manual_watch_url: Optional[str] = None

    # ENV KEY NAME that stores either:
    # - raw livestream API key, OR
    # - full livestream api url
    rumble_livestream_api_env_key: Optional[str] = None

    # Resolved at runtime (FULL URL)
    rumble_livestream_api_url: Optional[str] = None

    # Chat send (DOM)
    rumble_chat_channel_id: Optional[str] = None
    rumble_dom_chat_enabled: bool = True

    # -------------------------------------------------

    def platform_enabled(self, name: str) -> bool:
        return bool(self.platforms.get(name, False))

    # -------------------------------------------------

    def __post_init__(self):
        platform_state = (self.platform_states or {}).get("rumble")
        if platform_state in {PlatformState.PAUSED, PlatformState.DISABLED}:
            return

        if not self.platform_enabled("rumble"):
            return

        if not self.rumble_manual_watch_url:
            raise RuntimeError(
                f"[{self.creator_id}] rumble_manual_watch_url is REQUIRED"
            )

        if not self.rumble_livestream_api_env_key:
            raise RuntimeError(
                f"[{self.creator_id}] rumble_livestream_api_env_key is REQUIRED"
            )

        raw = os.getenv(self.rumble_livestream_api_env_key)
        if raw is None:
            raise RuntimeError(
                f"[{self.creator_id}] ENV VAR NOT FOUND: {self.rumble_livestream_api_env_key}"
            )

        raw = raw.strip()
        if not raw:
            raise RuntimeError(
                f"[{self.creator_id}] ENV VAR EMPTY: {self.rumble_livestream_api_env_key}"
            )

        # If env var contains full URL, use it directly (prevents double key=key= bugs)
        if raw.startswith("http://") or raw.startswith("https://"):
            self.rumble_livestream_api_url = raw
        else:
            # Otherwise treat as the key value and construct the URL
            self.rumble_livestream_api_url = (
                "https://rumble.com/-livestream-api/get-data?key=" + raw
            )
