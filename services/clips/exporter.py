from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

from shared.storage.state_publisher import DashboardStatePublisher
from services.clips.models import ClipRecord


class ClipStateExporter:
    """
    Publishes clip state snapshots for dashboard consumption.
    """

    def __init__(self, state_path: str):
        self._state_path = state_path
        self._publisher = DashboardStatePublisher()

    def build_payload(self, clips: List[ClipRecord]) -> Dict[str, object]:
        return {
            "schema_version": "v1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "clips": [
                {
                    "clip_id": clip.clip_id,
                    "creator_id": clip.creator_id,
                    "state": clip.state,
                    "source_title": clip.source_title,
                    "clipper_username": clip.clipper_username,
                    "requested_at": clip.requested_at,
                    "updated_at": clip.updated_at,
                    "output_path": clip.output_path,
                    "published_url": clip.published_url,
                    "last_error": clip.last_error,
                    "destination": {
                        "platform": clip.destination_platform,
                        "channel_url": clip.destination_channel_url,
                    },
                    "clip_title": clip.clip_title,
                }
                for clip in clips
            ],
        }

    def _normalized_state_path(self) -> Path:
        rel = Path(self._state_path)
        if rel.is_absolute():
            return Path(rel.name)

        # Normalize accidental prefixes like shared/state/<file>
        parts = rel.parts
        if len(parts) >= 2 and parts[0] == "shared" and parts[1] == "state":
            return Path(*parts[2:]) if len(parts) > 2 else Path("clips.json")
        return rel

    def publish(self, clips: List[ClipRecord]) -> None:
        payload = self.build_payload(clips)
        self._publisher.publish(self._normalized_state_path(), payload)
