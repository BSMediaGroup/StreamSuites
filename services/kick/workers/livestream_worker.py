from shared.logging.logger import get_logger

log = get_logger("kick.livestream_worker", runtime="streamsuites")


class KickLivestreamWorker:
    """Placeholder livestream worker for Kick.

    This stub documents the intended ingest path (stream state + chat socket)
    without performing any network operations. It can be wired into the
    scheduler once Kick endpoints are validated.
    """

    def __init__(self, *, ctx, channel: str):
        self.ctx = ctx
        self.channel = channel

    async def run(self) -> None:
        log.info(
            f"[{self.ctx.creator_id}] Kick livestream worker is stubbed; no-op run()"
        )

    async def shutdown(self) -> None:
        log.info(f"[{self.ctx.creator_id}] Kick livestream worker shutdown (stub)")
