"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.1-alpha (Build 2025.02)
Owner: Daniel Clancy
 Copyright © 2026 Brainstream Media Group
======================================================================
"""

"""
Discord runtime entrypoint (control-plane only).

This module launches the Discord control-plane runtime as an
independent process. It owns:

- event loop creation
- lifecycle wiring
- orderly startup and shutdown
- logging scope

IMPORTANT:
- This runtime MUST NOT launch streaming ingestion workers
- This runtime MUST NOT touch core/app.py responsibilities
- This runtime is fully optional and independently restartable
"""

import asyncio
import signal
import sys

from dotenv import load_dotenv

from shared.logging.logger import get_logger
from services.discord.runtime.supervisor import DiscordSupervisor

log = get_logger("core.discord_app")


# ----------------------------------------------------------------------
# MAIN ASYNC ENTRYPOINT
# ----------------------------------------------------------------------

async def main(stop_event: asyncio.Event):
    load_dotenv()

    log.info("Discord control-plane runtime booting")

    supervisor = DiscordSupervisor()

    # --------------------------------------------------
    # START DISCORD RUNTIME
    # --------------------------------------------------
    try:
        await supervisor.start()
        log.info("Discord supervisor started successfully")
    except Exception as e:
        log.error(f"Failed to start Discord supervisor: {e}")
        raise

    # --------------------------------------------------
    # BLOCK UNTIL SHUTDOWN SIGNAL
    # --------------------------------------------------
    await stop_event.wait()

    log.info("Discord shutdown initiated")

    # --------------------------------------------------
    # ORDERLY SHUTDOWN
    # --------------------------------------------------
    try:
        await supervisor.shutdown()
    except Exception as e:
        log.warning(f"Discord supervisor shutdown error ignored: {e}")

    log.info("Discord runtime stopped")


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
