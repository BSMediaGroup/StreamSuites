import asyncio
from typing import Dict, List

from core.context import CreatorContext
from services.rumble.workers.livestream_worker import RumbleLivestreamWorker
from shared.logging.logger import get_logger

log = get_logger("core.scheduler")


class Scheduler:
    def __init__(self):
        self._tasks: Dict[str, List[asyncio.Task]] = {}

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"Starting creator runtime: {ctx.creator_id}")
        self._tasks[ctx.creator_id] = []

        # Heartbeat (always on)
        heartbeat = asyncio.create_task(self._heartbeat(ctx))
        self._tasks[ctx.creator_id].append(heartbeat)

        # Rumble livestream + chat orchestration
        if ctx.platform_enabled("rumble"):
            livestream_worker = RumbleLivestreamWorker(
                ctx=ctx,
                jobs=self._get_job_registry()
            )
            task = asyncio.create_task(livestream_worker.run())
            self._tasks[ctx.creator_id].append(task)

    async def _heartbeat(self, ctx: CreatorContext):
        while True:
            log.debug(f"[{ctx.creator_id}] runtime heartbeat")
            await asyncio.sleep(10)

    async def shutdown(self):
        log.info("Scheduler shutdown initiated")

        for group in self._tasks.values():
            for task in group:
                task.cancel()

        await asyncio.gather(
            *[task for group in self._tasks.values() for task in group],
            return_exceptions=True
        )

    def _get_job_registry(self):
        from core.app import _GLOBAL_JOB_REGISTRY
        return _GLOBAL_JOB_REGISTRY
