import asyncio
import signal
import sys

from dotenv import load_dotenv

from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from shared.logging.logger import get_logger
from media.jobs.clip_job import ClipJob

# If your rumble browser client exists, keep this import.
# If it doesn't exist in your project yet, comment it out.
from services.rumble.browser.browser_client import RumbleBrowserClient


log = get_logger("core.app")

_GLOBAL_JOB_REGISTRY: JobRegistry | None = None


async def main(stop_event: asyncio.Event):
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

    # Wait for shutdown signal
    await stop_event.wait()

    log.info("Shutdown initiated")

    # Shutdown in a strict order: workers -> browser -> final log
    try:
        await scheduler.shutdown()
    except Exception as e:
        log.warning(f"Scheduler shutdown error ignored: {e}")

    try:
        # Ensure Playwright is torn down BEFORE loop closes.
        await RumbleBrowserClient.instance().shutdown()
    except Exception as e:
        log.warning(f"Browser shutdown error ignored: {e}")

    log.info("StreamSuites stopped")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event):
    """
    Windows-safe Ctrl+C handler:
    - signal.signal() works on Windows
    - we set an asyncio.Event so main() can unwind cleanly
    """
    def _handler(signum, frame):
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except Exception:
            # Worst case: just set it directly
            stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        # If signals are restricted, we still have KeyboardInterrupt fallback
        pass


def run():
    stop_event = asyncio.Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    _install_signal_handlers(loop, stop_event)

    try:
        loop.run_until_complete(main(stop_event))
    except KeyboardInterrupt:
        # If SIGINT didn't route through signal handlers for some reason:
        log.info("KeyboardInterrupt received (fallback) — shutdown initiated")
        try:
            stop_event.set()
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
    finally:
        # Cancel any remaining tasks cleanly
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for t in pending:
            t.cancel()

        if pending:
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass

        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass

        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    run()
    sys.exit(0)
