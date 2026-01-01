"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.2-alpha (Build 2025.03)
Owner: Daniel Clancy
 Copyright © 2026 Brainstream Media Group
======================================================================
"""

import asyncio
import signal
import sys

from dotenv import load_dotenv

from core.config_loader import ConfigLoader
from core.registry import CreatorRegistry
from core.scheduler import Scheduler
from core.jobs import JobRegistry
from core.state_exporter import runtime_snapshot_exporter, runtime_state
from shared.logging.logger import get_logger
from media.jobs.clip_job import ClipJob
from services.clips.manager import clip_manager

# >>> ADDITIVE: quota snapshot aggregation
from shared.runtime.quotas import quota_snapshot_aggregator
# <<< END ADDITIVE

log = get_logger("core.app")

_GLOBAL_JOB_REGISTRY: JobRegistry | None = None
RUNTIME_SNAPSHOT_INTERVAL = 10


async def main(stop_event: asyncio.Event):
    global _GLOBAL_JOB_REGISTRY
    clip_runtime_started = False

    # --------------------------------------------------
    # ENV
    # --------------------------------------------------
    load_dotenv()
    log.info("Environment variables loaded")
    log.info("StreamSuites booting")
    runtime_state.record_event(
        source="system",
        severity="info",
        message="Runtime boot sequence started",
    )

    # --------------------------------------------------
    # CONFIG INGESTION (DASHBOARD-COMPATIBLE)
    # --------------------------------------------------
    config_loader = ConfigLoader()
    restart_sources = config_loader.restart_intent_sources()
    runtime_state.record_restart_baseline(
        config_loader.compute_restart_baseline_hashes(), restart_sources
    )
    system_config = config_loader.load_system_config()
    platform_config = config_loader.load_platforms_config()
    creators_config = config_loader.load_creators_config()
    job_enable_flags = system_config.system.jobs

    # Seed runtime state for snapshot export (includes disabled creators)
    runtime_state.apply_platform_config(platform_config)
    runtime_state.apply_creators_config(creators_config)
    runtime_state.apply_system_config(
        {
            "platform_polling_enabled": system_config.system.platform_polling_enabled,
            "platforms": dict(system_config.system.platforms),
        }
    )
    runtime_state.apply_job_config(job_enable_flags)

    if not system_config.system.platform_polling_enabled:
        log.info(
            "[BOOT] Platform polling disabled by system config — chat workers will not start"
        )

    # --------------------------------------------------
    # LOAD CREATORS (runtime-enabled only)
    # --------------------------------------------------
    creators = CreatorRegistry(config_loader=config_loader).load(
        creators_data=creators_config,
        platform_defaults=platform_config,
    )
    log.info(f"Loaded {len(creators)} creator(s)")

    triggers_config, trigger_source = config_loader.load_triggers_config(
        creator_ids=list(creators.keys())
    )
    runtime_state.record_triggers_source(trigger_source)
    if triggers_config:
        log.info(
            f"Loaded {len(triggers_config)} trigger(s) for active creators from {trigger_source} config"
        )
    else:
        log.info("No triggers configured for active creators")

    # --------------------------------------------------
    # CORE SYSTEMS
    # --------------------------------------------------
    scheduler = Scheduler(
        platforms_config=platform_config,
        platform_polling_enabled=system_config.system.platform_polling_enabled,
        platform_enable_flags=system_config.system.platforms,
    )
    jobs = JobRegistry(job_enable_flags=job_enable_flags)
    _GLOBAL_JOB_REGISTRY = jobs

    # --------------------------------------------------
    # REGISTER JOB TYPES (FEATURE-GATED)
    # --------------------------------------------------
    clip_feature_enabled = any(
        getattr(ctx, "features", {}).get("clips", False)
        for ctx in creators.values()
    )
    clip_enabled = job_enable_flags.get("clips", True) and clip_feature_enabled

    if job_enable_flags.get("clips", True) and not clip_feature_enabled:
        log.info("Clip job NOT registered (no tier permits clips)")
    elif not job_enable_flags.get("clips", True):
        log.info("Clip job disabled via system config — registration skipped")
    if clip_enabled:
        jobs.register("clip", ClipJob)
        log.info("Clip job registered (tier feature enabled)")
        try:
            await clip_manager.start()
            clip_runtime_started = True
        except Exception as e:
            log.error(f"Clip runtime failed to start: {e}")

    # --------------------------------------------------
    # INITIAL SNAPSHOT EXPORT
    # --------------------------------------------------
    runtime_snapshot_exporter.publish()

    # --------------------------------------------------
    # START CREATOR RUNTIMES
    # --------------------------------------------------
    for ctx in creators.values():
        try:
            await scheduler.start_creator(ctx)
            log.info(f"[{ctx.creator_id}] Creator runtime started")
        except Exception as e:
            runtime_state.record_creator_error(ctx.creator_id, str(e))
            log.error(
                f"[{ctx.creator_id}] Failed to start creator runtime: {e}"
            )

    # ==================================================
    # ADDITIVE — GLOBAL QUOTA SNAPSHOT LOOP (READ-ONLY)
    # ==================================================

    async def _quota_snapshot_loop():
        log.info("Quota snapshot loop started (15s cadence)")
        try:
            while not stop_event.is_set():
                try:
                    quota_snapshot_aggregator.publish()
                except Exception as e:
                    log.warning(f"Quota snapshot publish failed: {e}")
                await asyncio.sleep(15)
        finally:
            log.info("Quota snapshot loop stopped")

    quota_task = asyncio.create_task(_quota_snapshot_loop())

    # ==================================================
    # RUNTIME SNAPSHOT LOOP (DASHBOARD READ-ONLY)
    # ==================================================

    async def _runtime_snapshot_loop():
        log.info(f"Runtime snapshot loop started ({RUNTIME_SNAPSHOT_INTERVAL}s cadence)")
        try:
            while not stop_event.is_set():
                try:
                    runtime_snapshot_exporter.publish()
                except Exception as e:
                    log.warning(f"Runtime snapshot publish failed: {e}")
                await asyncio.sleep(RUNTIME_SNAPSHOT_INTERVAL)
        finally:
            log.info("Runtime snapshot loop stopped")

    runtime_snapshot_task = asyncio.create_task(_runtime_snapshot_loop())

    # --------------------------------------------------
    # BLOCK UNTIL SHUTDOWN SIGNAL
    # --------------------------------------------------
    await stop_event.wait()

    log.info("Shutdown initiated")

    # --------------------------------------------------
    # ORDERLY SHUTDOWN — DELEGATED TO SCHEDULER
    # --------------------------------------------------
    try:
        await scheduler.shutdown()
    except Exception as e:
        log.warning(f"Scheduler shutdown error ignored: {e}")

    # --------------------------------------------------
    # STOP BACKGROUND LOOPS
    # --------------------------------------------------
    quota_task.cancel()
    runtime_snapshot_task.cancel()
    try:
        await quota_task
    except asyncio.CancelledError:
        pass
    try:
        await runtime_snapshot_task
    except asyncio.CancelledError:
        pass

    # --------------------------------------------------
    # CLIP RUNTIME SHUTDOWN
    # --------------------------------------------------
    if clip_runtime_started:
        try:
            await clip_manager.shutdown()
        except Exception as e:
            log.warning(f"Clip manager shutdown failed: {e}")

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
