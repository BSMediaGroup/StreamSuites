import asyncio
from typing import Optional

from core.jobs import JobRegistry
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.rumble.workers.chat_worker import RumbleChatWorker
from shared.logging.logger import get_logger

log = get_logger("rumble.livestream_worker")


class RumbleLivestreamWorker:
    """
    MODEL A — LIVESTREAM CONTROLLER (HARDENED)

    RULES:
    - Manual watch URL ONLY
    - Exactly ONE ChatWorker
    - ChatWorker owns navigation + polling
    - Livestream worker owns browser lifetime (start/shutdown)
    """

    def __init__(self, ctx, jobs: JobRegistry):
        self.ctx = ctx
        self.jobs = jobs

        self.browser = RumbleBrowserClient.instance()
        self.chat_task: Optional[asyncio.Task] = None
        self.chat_worker: Optional[RumbleChatWorker] = None
        self._running = False

    # ------------------------------------------------------------

    async def run(self):
        if self._running:
            log.warning(
                f"[{self.ctx.creator_id}] Livestream worker already running — ignoring duplicate start"
            )
            return

        self._running = True

        if not self.ctx.rumble_manual_watch_url:
            raise RuntimeError(
                f"[{self.ctx.creator_id}] rumble_manual_watch_url is REQUIRED"
            )

        try:
            await self.browser.start()
            await self.browser.ensure_logged_in()

            log.info(
                f"[{self.ctx.creator_id}] Livestream locked → {self.ctx.rumble_manual_watch_url}"
            )

            # Spawn ChatWorker ONCE
            if self.chat_task and not self.chat_task.done():
                log.warning(
                    f"[{self.ctx.creator_id}] Chat worker already running — duplicate start prevented"
                )
                return

            self.chat_worker = RumbleChatWorker(
                ctx=self.ctx,
                jobs=self.jobs,
                watch_url=self.ctx.rumble_manual_watch_url,
            )

            self.chat_task = asyncio.create_task(self.chat_worker.run())

            # Hard idle — lifecycle owner
            while self._running:
                await asyncio.sleep(5)
                if self.chat_task.done():
                    try:
                        self.chat_task.result()
                        log.info(
                            f"[{self.ctx.creator_id}] Chat worker completed — livestream loop exiting"
                        )
                    except Exception as e:
                        log.error(
                            f"[{self.ctx.creator_id}] Chat worker exited with error: {e}"
                        )
                    finally:
                        self._running = False
                        break

        except asyncio.CancelledError:
            log.info(f"[{self.ctx.creator_id}] Livestream worker cancelled")
            raise

        finally:
            await self._shutdown()

    # ------------------------------------------------------------

    async def _shutdown(self):
        log.info(f"[{self.ctx.creator_id}] Livestream worker shutting down")

        if self.chat_task and not self.chat_task.done():
            self.chat_task.cancel()
            try:
                await self.chat_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.error(
                    f"[{self.ctx.creator_id}] Chat worker shutdown error: {e}"
                )

        self.chat_task = None
        self.chat_worker = None
        try:
            await self.browser.shutdown()
        except Exception as e:
            log.warning(f"[{self.ctx.creator_id}] Browser shutdown error: {e}")
        self._running = False
