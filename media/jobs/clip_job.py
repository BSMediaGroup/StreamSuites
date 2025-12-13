import asyncio
from core.jobs import Job
from shared.logging.logger import get_logger

log = get_logger("media.clip_job")


class ClipJob(Job):
    async def run(self):
        length = self.payload.get("length", 30)
        log.info(
            f"[{self.ctx.creator_id}] Simulating clip job ({length}s)"
        )

        # Simulate capture + processing
        await asyncio.sleep(2)

        log.info(
            f"[{self.ctx.creator_id}] Clip job complete"
        )
