from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared.logging.logger import get_logger

log = get_logger("services.clips.uploader")


@dataclass
class UploadResult:
    published_url: str
    detail: Optional[str] = None


class RumbleUploader:
    """
    Placeholder uploader that preserves deterministic state transitions.

    Actual Rumble upload wiring can replace the publish() method without
    changing the call sites or lifecycle.
    """

    def __init__(self, channel_url: str):
        self._channel_url = channel_url

    async def publish(self, clip_id: str, media_path: Path) -> UploadResult:
        """
        Simulated upload for deterministic workflows.
        """
        # Real integration would authenticate using env vars:
        # RUMBLE_BOT_USERNAME_DANIEL, RUMBLE_LIVESTREAM_KEY_DANIEL
        log.info(
            f"[{clip_id}] Uploading clip to Rumble destination {self._channel_url} "
            f"(file={media_path})"
        )

        # Deterministic placeholder URL for dashboard visibility
        url = f"{self._channel_url.rstrip('/')}/clip/{clip_id}"
        log.info(f"[{clip_id}] Upload complete → {url}")
        return UploadResult(published_url=url, detail="rumble-upload-simulated")
