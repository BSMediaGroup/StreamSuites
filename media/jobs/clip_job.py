import asyncio
import time

from core.jobs import Job
from shared.logging.logger import get_logger

log = get_logger("media.clip_job")


class ClipJob(Job):
    """
    ClipJob enforces tier-resolved clip limits at runtime.

    This job MUST NOT know about tiers.
    It consumes resolved limits from ctx.limits only.
    """

    async def run(self):
        creator_id = self.ctx.creator_id
        limits = self.ctx.limits.get("clips", {})

        # --------------------------------------------------
        # LIMITS (RESOLVED, AUTHORITATIVE)
        # --------------------------------------------------

        enabled = limits.get("enabled", False)
        max_duration = limits.get("max_duration_seconds", 0)
        min_cooldown = limits.get("min_cooldown_seconds", 0)
        max_concurrent = limits.get("max_concurrent_jobs", 0)

        # --------------------------------------------------
        # BASIC ENABLE CHECK
        # --------------------------------------------------

        if not enabled:
            log.warning(
                f"[{creator_id}] Clip job rejected: clips disabled by limits"
            )
            return

        # --------------------------------------------------
        # PAYLOAD
        # --------------------------------------------------

        requested_length = int(self.payload.get("length", 30))
        effective_length = min(requested_length, max_duration)

        if requested_length > max_duration:
            log.warning(
                f"[{creator_id}] Clip length capped "
                f"({requested_length}s → {effective_length}s)"
            )

        # --------------------------------------------------
        # CONCURRENCY ENFORCEMENT
        # --------------------------------------------------

        active = self.scheduler.count_active_jobs(
            creator_id=creator_id,
            job_type="clip",
        )

        if active >= max_concurrent:
            log.warning(
                f"[{creator_id}] Clip job rejected: "
                f"max concurrent clip jobs reached ({active}/{max_concurrent})"
            )
            return

        # --------------------------------------------------
        # COOLDOWN ENFORCEMENT
        # --------------------------------------------------

        now = time.time()
        last = self.scheduler.get_last_job_time(
            creator_id=creator_id,
            job_type="clip",
        )

        if last is not None:
            delta = now - last
            if delta < min_cooldown:
                remaining = round(min_cooldown - delta, 2)
                log.warning(
                    f"[{creator_id}] Clip job rejected: "
                    f"cooldown active ({remaining}s remaining)"
                )
                return

        # --------------------------------------------------
        # EXECUTION (SIMULATED)
        # --------------------------------------------------

        log.info(
            f"[{creator_id}] Starting clip job ({effective_length}s)"
        )

        # Simulate capture + processing
        await asyncio.sleep(2)

        log.info(
            f"[{creator_id}] Clip job complete ({effective_length}s)"
        )
