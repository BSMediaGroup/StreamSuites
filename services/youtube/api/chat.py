import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional, Set

import httpx

from services.youtube.models.message import YouTubeChatMessage
from shared.logging.logger import get_logger
from shared.runtime.quotas import (
    quota_registry,
    QuotaExceeded,
    QuotaBufferWarning,
)

log = get_logger("youtube.chat", runtime="streamsuites")


class YouTubeChatClient:
    """
    Polling client for YouTube Live Chat via the Data API v3.

    Responsibilities:
    - Poll liveChat/messages endpoint
    - Respect server-provided polling intervals
    - Deduplicate messages
    - Normalize payloads into YouTubeChatMessage
    - Enforce YouTube API quota limits (runtime-authoritative)
    - Remain cancellation-safe and deterministic
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3/liveChat/messages"

    # YouTube Data API v3 cost
    QUOTA_COST_PER_CALL = 5

    def __init__(
        self,
        *,
        api_key: str,
        live_chat_id: str,
        creator_id: str,
        limits: Dict[str, int],
        poll_interval: float = 2.5,
    ):
        if not api_key:
            raise RuntimeError("YouTube API key is required")
        if not live_chat_id:
            raise RuntimeError("YouTube live_chat_id is required")
        if not creator_id:
            raise RuntimeError("creator_id is required for quota enforcement")

        self.api_key = api_key
        self.live_chat_id = live_chat_id
        self.creator_id = creator_id
        self.poll_interval = poll_interval

        # --------------------------------------------------
        # Quota registration (AUTHORITATIVE)
        # --------------------------------------------------

        max_units = limits.get("youtube_daily_units_max", 0)
        buffer_units = limits.get("youtube_daily_units_buffer", 0)

        self.quota_tracker = None

        if max_units:
            self.quota_tracker = quota_registry.register(
                creator_id=creator_id,
                platform="youtube",
                max_units=max_units,
                buffer_units=buffer_units,
            )
        else:
            log.warning(
                f"[YouTube][{self.creator_id}] "
                "youtube_daily_units_max not set — quota enforcement disabled"
            )

        # --------------------------------------------------

        self._page_token: Optional[str] = None
        self._stop_event = asyncio.Event()
        self._seen_ids: Set[str] = set()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def iter_messages(self) -> AsyncGenerator[YouTubeChatMessage, None]:
        """
        Poll YouTube live chat and yield normalized messages.

        Uses nextPageToken and pollingIntervalMillis as advised
        by the YouTube Data API.
        """
        self._stop_event.clear()

        params = {
            "part": "snippet,authorDetails",
            "liveChatId": self.live_chat_id,
            "key": self.api_key,
        }

        log.info(
            f"[YouTube][{self.creator_id}] "
            f"Starting live chat polling (liveChatId={self.live_chat_id})"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            while not self._stop_event.is_set():

                # -------------------------------
                # QUOTA ENFORCEMENT (PRE-CALL)
                # -------------------------------
                if self.quota_tracker:
                    try:
                        self.quota_tracker.consume(self.QUOTA_COST_PER_CALL)
                    except QuotaBufferWarning as warn:
                        log.warning(
                            f"[YouTube][{self.creator_id}] {warn}"
                        )
                    except QuotaExceeded as fatal:
                        log.error(
                            f"[YouTube][{self.creator_id}] {fatal} — polling halted"
                        )
                        return

                if self._page_token:
                    params["pageToken"] = self._page_token

                try:
                    response = await client.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.warning(
                        f"[YouTube][{self.creator_id}] chat poll error: {e}"
                    )
                    await asyncio.sleep(self.poll_interval)
                    continue

                self._page_token = data.get("nextPageToken")

                items = data.get("items", [])
                for item in items:
                    msg_id = item.get("id")
                    if not msg_id or msg_id in self._seen_ids:
                        continue

                    self._seen_ids.add(msg_id)
                    yield self._normalize_message(item)

                # Respect server-recommended polling interval
                interval_ms = data.get("pollingIntervalMillis")
                sleep_seconds = (
                    interval_ms / 1000.0
                    if isinstance(interval_ms, (int, float))
                    else self.poll_interval
                )

                snapshot = (
                    self.quota_tracker.snapshot()
                    if self.quota_tracker
                    else None
                )

                log.debug(
                    f"[YouTube][{self.creator_id}] Poll complete "
                    f"(messages={len(items)}, "
                    f"quota={snapshot}, "
                    f"sleep={sleep_seconds}s)"
                )

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=sleep_seconds,
                    )
                except asyncio.TimeoutError:
                    pass

        log.info(
            f"[YouTube][{self.creator_id}] Live chat polling stopped"
        )

    async def close(self) -> None:
        """
        Signal polling loop to stop.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    # Normalization helpers
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
