import asyncio

from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from shared.logging.logger import get_logger

log = get_logger("core.app")


async def main():
    log.info("StreamSuites booting")

    creators = CreatorRegistry().load()
    scheduler = Scheduler()
    jobs = JobRegistry()

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
