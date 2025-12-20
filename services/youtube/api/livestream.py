import httpx
from typing import Optional

from services.youtube.models.stream import YouTubeLivestream
from shared.logging.logger import get_logger

log = get_logger("youtube.livestream", runtime="streamsuites")


class YouTubeLivestreamAPI:
    """
    YouTube livestream discovery API (Data API v3).

    Responsibilities:
    - Resolve channel ID from channel ID or @handle
    - Detect active live broadcast for the channel
    - Resolve activeLiveChatId
    - Return normalized YouTubeLivestream metadata

    This module is read-only and safe to call repeatedly.
    """

    CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
    SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, *, api_key: str):
        if not api_key:
            raise RuntimeError("YouTube API key is required")
        self.api_key = api_key

    # ------------------------------------------------------------

    async def get_active_livestream(
        self,
        *,
        channel_id: str,
    ) -> Optional[YouTubeLivestream]:
        """
        Resolve the active livestream for a channel and return normalized metadata.

        `channel_id` may be:
        - A YouTube channel ID (UCxxxx)
        - A channel handle (e.g. "@StreamSuites")
        """

        resolved_channel_id = await self._resolve_channel_id(channel_id)
        if not resolved_channel_id:
            log.info(f"YouTube channel not found: {channel_id}")
            return None

        live_video_id = await self._find_live_video_id(resolved_channel_id)
        if not live_video_id:
            log.debug(
                f"[YouTube] No active livestream for channel {resolved_channel_id}"
            )
            return None

        return await self._resolve_livestream_details(live_video_id)

    # ------------------------------------------------------------
    # Channel resolution
    # ------------------------------------------------------------

    async def _resolve_channel_id(self, identifier: str) -> Optional[str]:
        """
        Resolve a channel ID from a channel ID or @handle.
        """
        params = {
            "part": "id",
            "key": self.api_key,
        }

        if identifier.startswith("@"):
            params["forHandle"] = identifier.lstrip("@")
        else:
            params["id"] = identifier

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.CHANNELS_URL, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning(f"YouTube channel resolution error: {e}")
                return None

        items = data.get("items", [])
        if not items:
            return None

        return items[0].get("id")

    # ------------------------------------------------------------
    # Live video discovery
    # ------------------------------------------------------------

    async def _find_live_video_id(self, channel_id: str) -> Optional[str]:
        """
        Find the currently live video for a channel.
        """
        params = {
            "part": "id",
            "channelId": channel_id,
            "eventType": "live",
            "type": "video",
            "maxResults": 1,
            "key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.SEARCH_URL, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning(f"YouTube live search error: {e}")
                return None

        items = data.get("items", [])
        if not items:
            return None

        return items[0].get("id", {}).get("videoId")

    # ------------------------------------------------------------
    # Livestream metadata
    # ------------------------------------------------------------

    async def _resolve_livestream_details(
        self,
        video_id: str,
    ) -> Optional[YouTubeLivestream]:
        """
        Resolve livestream details including activeLiveChatId.
        """
        params = {
            "part": "snippet,liveStreamingDetails",
            "id": video_id,
            "key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(self.VIDEOS_URL, params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning(f"YouTube livestream detail error: {e}")
                return None

        items = data.get("items", [])
        if not items:
            return None

        item = items[0]
        snippet = item.get("snippet", {})
        live_details = item.get("liveStreamingDetails", {})

        live_chat_id = live_details.get("activeLiveChatId")
        if not live_chat_id:
            return None

        return YouTubeLivestream(
            raw=item,
            video_id=video_id,
            channel_id=snippet.get("channelId"),
            title=snippet.get("title"),
            live_chat_id=live_chat_id,
            started_at=live_details.get("actualStartTime"),
            is_live=True,
        )
