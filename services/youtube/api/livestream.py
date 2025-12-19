
from typing import Optional

from services.youtube.models.stream import YouTubeLivestream
from shared.logging.logger import get_logger

log = get_logger("youtube.livestream", runtime="streamsuites")


class YouTubeLivestreamAPI:
    """
    Scaffold for YouTube livestream discovery.

    Responsibility:
    - Resolve the active `liveChatId` for a channel/stream
    - Provide lightweight stream metadata for dashboard/state publication

    Implementation is deferred until API keys and quotas are provisioned. The
    contract mirrors Twitch scaffolding so workers can be wired into the
    scheduler when ready.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3/liveBroadcasts"

    def __init__(self, *, api_key: str):
        if not api_key:
            raise RuntimeError("YouTube API key is required")
        self.api_key = api_key

    async def get_active_livestream(
        self,
        *,
        channel_id: str,
    ) -> Optional[YouTubeLivestream]:
        """
        Fetch the current live broadcast and return normalized metadata.
        """
        raise NotImplementedError(
            "YouTube livestream lookup is scaffolded only; implement later."
        )
