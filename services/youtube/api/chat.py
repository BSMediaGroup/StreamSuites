
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional

from services.youtube.models.message import YouTubeChatMessage
from shared.logging.logger import get_logger

log = get_logger("youtube.chat", runtime="streamsuites")


class YouTubeChatClient:
    """
    Scaffold for polling YouTube live chat via the Data API.

    Implementation is intentionally deferred; this class encodes the contract
    and normalization expectations used by workers and future trigger routing.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3/liveChat/messages"

    def __init__(
        self,
        *,
        api_key: str,
        live_chat_id: str,
        poll_interval: float = 2.5,
    ):
        if not api_key:
            raise RuntimeError("YouTube API key is required")
        if not live_chat_id:
            raise RuntimeError("YouTube live_chat_id is required")

        self.api_key = api_key
        self.live_chat_id = live_chat_id
        self.poll_interval = poll_interval

        self._page_token: Optional[str] = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def iter_messages(self) -> AsyncGenerator[YouTubeChatMessage, None]:
        """
        Poll YouTube live chat and yield normalized messages.

        The Data API returns `pollingIntervalMillis` to suggest backoff; this
        scaffold stores the page token and interval hints but intentionally
        defers the network implementation.
        """
        self._stop_event.clear()
        log.info(
            f"[YouTube] Polling live chat {self.live_chat_id} "
            f"(interval={self.poll_interval}s) — implementation pending"
        )
        raise NotImplementedError(
            "YouTube chat polling is scaffolded only; implement API calls later."
        )
        yield  # pragma: no cover (generator form placeholder)

    async def close(self) -> None:
        """
        Placeholder close hook for parity with other platform clients.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    # Normalization helpers (placeholders)
    # ------------------------------------------------------------------ #

    def _normalize_message(self, payload: Dict) -> YouTubeChatMessage:
        """
        Convert a YouTube liveChatMessage resource into a normalized shape.
        """
        snippet = payload.get("snippet", {})
        author_details = payload.get("authorDetails", {})

        return YouTubeChatMessage(
            raw=payload,
            live_chat_id=snippet.get("liveChatId", self.live_chat_id),
            message_id=payload.get("id"),
            author_name=author_details.get("displayName") or "unknown",
            author_channel_id=author_details.get("channelId"),
            text=snippet.get("displayMessage") or "",
            published_at=self._parse_published_at(snippet.get("publishedAt")),
            is_owner=bool(author_details.get("isChatOwner")),
            is_moderator=bool(author_details.get("isChatModerator")),
            is_member=bool(author_details.get("isChatSponsor")),
            superchat_amount=None,
            superchat_currency=None,
            badges=[
                badge
                for badge in [
                    "owner" if author_details.get("isChatOwner") else None,
                    "moderator" if author_details.get("isChatModerator") else None,
                    "member" if author_details.get("isChatSponsor") else None,
                ]
                if badge
            ],
        )

    @staticmethod
    def _parse_published_at(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return ts.astimezone(timezone.utc)
        except Exception:
            return None
