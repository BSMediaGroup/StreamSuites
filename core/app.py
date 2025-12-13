import asyncio
import sys

from dotenv import load_dotenv

from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from shared.logging.logger import get_logger
from media.jobs.clip_job import ClipJob
from services.rumble.browser.browser_client import RumbleBrowserClient


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
        # Keep the event loop alive without busy waiting
        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        # Normal during shutdown
        pass

    finally:
        log.info("Shutdown initiated")

        # Stop scheduled workers first
        await scheduler.shutdown()

        # Shutdown Playwright browser cleanly
        await RumbleBrowserClient.instance().shutdown()

        log.info("StreamSuites stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
