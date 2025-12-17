import asyncio
import signal
import sys

from dotenv import load_dotenv

from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from shared.logging.logger import get_logger
from media.jobs.clip_job import ClipJob

# IMPORTANT: browser cleanup hook
from services.rumble.browser.browser_client import RumbleBrowserClient

log = get_logger("core.app")

_GLOBAL_JOB_REGISTRY: JobRegistry | None = None


async def main(stop_event: asyncio.Event):
    global _GLOBAL_JOB_REGISTRY

    # --------------------------------------------------
    # ENV
    # --------------------------------------------------
    load_dotenv()
    log.info("Environment variables loaded")
    log.info("StreamSuites booting")

    # --------------------------------------------------
    # LOAD CREATORS
    # --------------------------------------------------
    creators = CreatorRegistry().load()
    log.info(f"Loaded {len(creators)} creator(s)")

    # --------------------------------------------------
    # CORE SYSTEMS
    # --------------------------------------------------
    scheduler = Scheduler()
    jobs = JobRegistry()
    _GLOBAL_JOB_REGISTRY = jobs

    # --------------------------------------------------
    # REGISTER JOB TYPES (FEATURE-GATED)
    # --------------------------------------------------
    clip_enabled = any(
        getattr(ctx, "features", {}).get("clips", False)
        for ctx in creators.values()
    )

    if clip_enabled:
        jobs.register("clip", ClipJob)
        log.info("Clip job registered (tier feature enabled)")
    else:
        log.info("Clip job NOT registered (no tier permits clips)")

    # --------------------------------------------------
    # START CREATOR RUNTIMES
    # --------------------------------------------------
    for ctx in creators.values():
        try:
            await scheduler.start_creator(ctx)
            log.info(f"[{ctx.creator_id}] Creator runtime started")
        except Exception as e:
            log.error(
                f"[{ctx.creator_id}] Failed to start creator runtime: {e}"
            )

    # --------------------------------------------------
    # BLOCK UNTIL SHUTDOWN SIGNAL
    # --------------------------------------------------
    await stop_event.wait()

    log.info("Shutdown initiated")

    # --------------------------------------------------
    # ORDERLY SHUTDOWN — TASKS FIRST
    # --------------------------------------------------
    try:
        await scheduler.shutdown()
    except Exception as e:
        log.warning(f"Scheduler shutdown error ignored: {e}")

    # --------------------------------------------------
    # BROWSER CLEANUP (CRITICAL FOR MODEL A)
    # --------------------------------------------------
    try:
        browser = RumbleBrowserClient.instance()
        await browser.shutdown()
        log.info("Rumble browser shutdown complete")
    except Exception as e:
        log.warning(f"Browser shutdown error ignored: {e}")

    log.info("StreamSuites stopped")


# ----------------------------------------------------------------------
# SIGNAL HANDLING (WINDOWS-SAFE)
# ----------------------------------------------------------------------

def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
):
    """
    Windows-safe Ctrl+C handler.
    Uses signal.signal + asyncio.Event to unwind cleanly.
    """

    def _handler(signum, frame):
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except Exception:
            stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        pass


# ----------------------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------------------

def run():
    stop_event = asyncio.Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    _install_signal_handlers(loop, stop_event)

    try:
        loop.run_until_complete(main(stop_event))

    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received — shutdown initiated")
        try:
            stop_event.set()
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass

    finally:
        # --------------------------------------------------
        # CANCEL REMAINING TASKS (CLEANLY)
        # --------------------------------------------------
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()

        if pending:
            try:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            except Exception:
                pass

        # --------------------------------------------------
        # FINAL LOOP CLEANUP
        # --------------------------------------------------
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass

        asyncio.set_event_loop(None)
        loop.close()


if __name__ == "__main__":
    run()
    sys.exit(0)
