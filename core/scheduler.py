import asyncio
from typing import Dict, List

from core.context import CreatorContext
from services.rumble.workers.livestream_worker import RumbleLivestreamWorker
from shared.logging.logger import get_logger

log = get_logger("core.scheduler")


class Scheduler:
    def __init__(self):
        # creator_id -> list[asyncio.Task]
        self._tasks: Dict[str, List[asyncio.Task]] = {}

    # ------------------------------------------------------------

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"Starting creator runtime: {ctx.creator_id}")

        if ctx.creator_id in self._tasks:
            log.warning(f"[{ctx.creator_id}] runtime already started")
            return

        self._tasks[ctx.creator_id] = []

        # --------------------------------------------------
        # Heartbeat (always on)
        # --------------------------------------------------
        heartbeat = asyncio.create_task(self._heartbeat(ctx))
        self._tasks[ctx.creator_id].append(heartbeat)

        # --------------------------------------------------
        # Rumble livestream + chat orchestration
        # --------------------------------------------------
        if ctx.platform_enabled("rumble"):
            livestream_worker = RumbleLivestreamWorker(
                ctx=ctx,
                jobs=self._get_job_registry()
            )
            task = asyncio.create_task(livestream_worker.run())
            self._tasks[ctx.creator_id].append(task)

    # ------------------------------------------------------------

    async def _heartbeat(self, ctx: CreatorContext):
        try:
            while True:
                log.debug(f"[{ctx.creator_id}] runtime heartbeat")
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            log.debug(f"[{ctx.creator_id}] heartbeat cancelled")
            raise

    # ------------------------------------------------------------

    async def shutdown(self):
        log.info("Scheduler shutdown initiated")

        # Flatten all tasks
        all_tasks: List[asyncio.Task] = [
            task
            for group in self._tasks.values()
            for task in group
        ]

        if not all_tasks:
            log.info("Scheduler shutdown: no active tasks")
            return

        # --------------------------------------------------
        # CANCEL FIRST
        # --------------------------------------------------
        for task in all_tasks:
            if not task.done():
                task.cancel()

        # --------------------------------------------------
        # AWAIT CANCELLATION
        # --------------------------------------------------
        results = await asyncio.gather(
            *all_tasks,
            return_exceptions=True
        )

        # --------------------------------------------------
        # LOG ABNORMAL EXITS (OPTIONAL BUT USEFUL)
        # --------------------------------------------------
        for result in results:
            if isinstance(result, Exception) and not isinstance(
                result, asyncio.CancelledError
            ):
                log.debug(f"Task exited with exception during shutdown: {result}")

        self._tasks.clear()

        log.info("Scheduler shutdown complete")

    # ------------------------------------------------------------

    def _get_job_registry(self):
        from core.app import _GLOBAL_JOB_REGISTRY
        return _GLOBAL_JOB_REGISTRY
