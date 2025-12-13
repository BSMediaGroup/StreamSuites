import asyncio
import os

from dotenv import load_dotenv

from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from shared.logging.logger import get_logger
from media.jobs.clip_job import ClipJob


log = get_logger("core.app")

_GLOBAL_JOB_REGISTRY: JobRegistry | None = None


async def main():
    global _GLOBAL_JOB_REGISTRY

    # Load environment variables
    load_dotenv()
    log.info("Environment variables loaded")

    log.info("StreamSuites booting")

    # Load creators
    creators = CreatorRegistry().load()

    # Initialize core systems
    scheduler = Scheduler()
    jobs = JobRegistry()

    _GLOBAL_JOB_REGISTRY = jobs

    # Register job types
    jobs.register("clip", ClipJob)

    # Start per-creator runtimes
    for ctx in creators.values():
        await scheduler.start_creator(ctx)

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutdown signal received")
    finally:
        await scheduler.shutdown()
        log.info("StreamSuites stopped")


if __name__ == "__main__":
    asyncio.run(main())
