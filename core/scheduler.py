import asyncio
from typing import Dict, List

from core.context import CreatorContext
from services.rumble.workers.chat_worker import RumbleChatWorker
from shared.logging.logger import get_logger

log = get_logger("core.scheduler")


class Scheduler:
    def __init__(self):
        self._tasks: Dict[str, List[asyncio.Task]] = {}

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"Starting creator runtime: {ctx.creator_id}")
        self._tasks[ctx.creator_id] = []

        heartbeat = asyncio.create_task(self._heartbeat(ctx))
        self._tasks[ctx.creator_id].append(heartbeat)

        if ctx.platform_enabled("rumble"):
            # NOTE: room_id will later be discovered dynamically
            # For now this is a placeholder to prove ingestion works
            room_id = "PLACEHOLDER_ROOM_ID"

            chat_worker = RumbleChatWorker(
                ctx=ctx,
                jobs=self._get_job_registry(),
                room_id=room_id
            )

            task = asyncio.create_task(chat_worker.run())
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
            *[t for group in self._tasks.values() for t in group],
            return_exceptions=True
        )

    def _get_job_registry(self):
        """
        This is injected indirectly via core.app.
        It will be replaced with proper DI shortly.
        """
        from core.app import _GLOBAL_JOB_REGISTRY
        return _GLOBAL_JOB_REGISTRY
