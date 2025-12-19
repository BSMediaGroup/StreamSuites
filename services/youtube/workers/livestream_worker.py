
from typing import Optional

from services.youtube.api.livestream import YouTubeLivestreamAPI
from services.youtube.models.stream import YouTubeLivestream
from shared.logging.logger import get_logger

log = get_logger("youtube.livestream_worker", runtime="streamsuites")


class YouTubeLivestreamWorker:
    """
    Scheduler-owned livestream discovery worker for YouTube.

    Responsibilities:
    - Resolve the active liveChatId for a channel and surface metadata
    - Prepare chat workers with the correct identifiers
    - Remain cancellation-safe and side-effect free on import
    """

    def __init__(
        self,
        *,
        ctx,
        api_key: str,
        channel_id: str,
    ):
        if not api_key:
            raise RuntimeError("YouTube api_key is required")
        if not channel_id:
            raise RuntimeError("YouTube channel_id is required")

        self.ctx = ctx
        self.channel_id = channel_id
        self._api = YouTubeLivestreamAPI(api_key=api_key)
        self.active_stream: Optional[YouTubeLivestream] = None

    # ------------------------------------------------------------------ #

    async def run(self) -> Optional[YouTubeLivestream]:
        log.info(
            f"[{self.ctx.creator_id}] YouTube livestream worker starting "
            f"for channel {self.channel_id}"
        )
        try:
            self.active_stream = await self._api.get_active_livestream(
                channel_id=self.channel_id
            )
        except NotImplementedError as e:
            log.info(f"[{self.ctx.creator_id}] {e}")
        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Livestream lookup error: {e}")
        else:
            if self.active_stream and self.active_stream.live_chat_id:
                log.info(
                    f"[{self.ctx.creator_id}] Active liveChatId resolved: "
                    f"{self.active_stream.live_chat_id}"
                )
            else:
                log.info(
                    f"[{self.ctx.creator_id}] No active YouTube livestream found"
                )

        return self.active_stream
