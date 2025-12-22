import asyncio
import time

from core.jobs import Job
from services.clips.manager import clip_manager
from services.clips.models import ClipDestination, ClipRequest
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
        limits = self.ctx.limits or {}
        feature_clips = getattr(self.ctx, "features", {}).get("clips", {}) if isinstance(getattr(self.ctx, "features", {}), dict) else {}

        # --------------------------------------------------
        # LIMITS (RESOLVED, AUTHORITATIVE)
        # --------------------------------------------------

        enabled = bool(feature_clips.get("enabled", False))
        max_duration = limits.get(
            "clip_max_duration_seconds",
            feature_clips.get("max_duration_seconds", 0)
        )
        min_cooldown = limits.get(
            "clip_min_cooldown_seconds",
            feature_clips.get("min_cooldown_seconds", 0)
        )
        max_concurrent = limits.get(
            "max_concurrent_clip_jobs",
            feature_clips.get("max_concurrent_jobs", 0)
        )

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

        # Guard: if max_duration is 0/None, treat as "no cap"
        try:
            max_duration_int = int(max_duration)
        except Exception:
            max_duration_int = 0

        if max_duration_int > 0:
            effective_length = min(requested_length, max_duration_int)
        else:
            effective_length = requested_length

        if max_duration_int > 0 and requested_length > max_duration_int:
            log.warning(
                f"[{creator_id}] Clip length capped "
                f"({requested_length}s → {effective_length}s)"
            )

        # --------------------------------------------------
        # CONCURRENCY ENFORCEMENT
        # --------------------------------------------------
        # NOTE:
        # Concurrency is enforced AUTHORITATIVELY in core/jobs.py (JobRegistry.dispatch)
        # using ctx.limits["max_concurrent_clip_jobs"] (or the tier-resolved equivalent).
        #
        # This job does NOT own job queue policy and has no scheduler/registry handle.
        # Keep the variables here for future UI visibility and policy alignment.
        _ = max_concurrent  # intentionally unused for now

        # --------------------------------------------------
        # COOLDOWN ENFORCEMENT
        # --------------------------------------------------
        # NOTE:
        # Cooldown requires a persisted "last successful clip time" store + wiring.
        # That plumbing does not exist yet in the current runtime, so enforcing here
        # would be a runtime error. We will implement cooldown centrally later.
        _ = min_cooldown  # intentionally unused for now
        _ = time.time()   # placeholder to keep imports stable

        # --------------------------------------------------
        # EXECUTION
        # --------------------------------------------------

        source_path = self.payload.get("source_path")
        if not source_path:
            log.warning(f"[{creator_id}] Clip job rejected: source_path missing")
            return

        start_seconds = float(self.payload.get("start_seconds", 0.0))
        clipper_username = str(self.payload.get("clipper_username", "anonymous"))
        source_title = str(self.payload.get("source_title", "Livestream"))

        destination_override = ClipDestination.from_dict(
            self.payload.get("destination_override")
        ) if self.payload.get("destination_override") else None

        request = ClipRequest(
            creator_id=creator_id,
            source_title=source_title,
            clipper_username=clipper_username,
            source_path=source_path,
            start_seconds=start_seconds,
            duration_seconds=effective_length,
            requested_by=self.payload.get("requested_by"),
            destination_override=destination_override,
        )

        # Enqueue clip for background processing
        record = clip_manager.enqueue_clip(request)
        log.info(
            f"[{creator_id}] Clip queued ({record.clip_id}) for {record.duration_seconds}s "
            f"starting at {start_seconds}s"
        )

        # Yield control to let the background worker start
        await asyncio.sleep(0)
