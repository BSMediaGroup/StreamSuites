import asyncio
from typing import Dict, List

from core.context import CreatorContext
from shared.logging.logger import get_logger

log = get_logger("core.scheduler")


class Scheduler:
    def __init__(self):
        self._tasks: Dict[str, List[asyncio.Task]] = {}

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"Starting creator runtime: {ctx.creator_id}")
        self._tasks[ctx.creator_id] = []

        task = asyncio.create_task(self._heartbeat(ctx))
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
