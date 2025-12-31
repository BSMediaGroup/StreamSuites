import asyncio
import uuid
import time
from typing import Dict, Optional, Type

from shared.logging.logger import get_logger
from shared.storage.state_store import append_job, update_job

log = get_logger("core.jobs")


class Job:
    def __init__(self, ctx, payload: dict):
        self.id = str(uuid.uuid4())
        self.ctx = ctx
        self.payload = payload
        self.status = "pending"
        self.created_at = int(time.time())
        self.started_at = None
        self.completed_at = None
        self.updated_at = self.created_at

    async def run(self):
        raise NotImplementedError


class JobRegistry:
    def __init__(self, job_enable_flags: Optional[Dict[str, bool]] = None):
        self._job_types: Dict[str, Type[Job]] = {}
        self._active_jobs: Dict[str, asyncio.Task] = {}
        self._job_enable_flags: Dict[str, bool] = self._normalize_job_flags(job_enable_flags)

        # --------------------------------------------------
        # METRICS (READ-ONLY, ADDITIVE)
        # --------------------------------------------------
        # These counters are observational only.
        # They do NOT affect scheduling or execution.
        self._metrics = {
            "dispatched": 0,
            "completed": 0,
            "failed": 0,
        }

    # ------------------------------------------------------------

    def register(self, name: str, job_cls: Type[Job]):
        self._job_types[name] = job_cls
        log.info(f"Registered job type: {name}")

    # ------------------------------------------------------------

    def _count_active_jobs(self, creator_id: str, job_type: str) -> int:
        """
        Count currently running jobs for a creator + job type.
        Deterministic and class-name independent.
        """
        count = 0
        for task in self._active_jobs.values():
            if task.done():
                continue

            t_creator = getattr(task, "_creator_id", None)
            t_type = getattr(task, "_job_type", None)

            if t_creator == creator_id and t_type == job_type:
                count += 1

        return count

    # ------------------------------------------------------------
    # READ-ONLY VISIBILITY HOOKS (SAFE FOR DASHBOARD)
    # ------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        """
        Returns global job metrics (read-only).
        """
        return dict(self._metrics)

    def get_active_job_counts(self) -> Dict[str, int]:
        """
        Returns active job counts by job_type.
        """
        counts: Dict[str, int] = {}

        for task in self._active_jobs.values():
            if task.done():
                continue

            job_type = getattr(task, "_job_type", None)
            if not job_type:
                continue

            counts[job_type] = counts.get(job_type, 0) + 1

        return counts

    # ------------------------------------------------------------

    @staticmethod
    def _normalize_job_flags(job_enable_flags: Optional[Dict[str, bool]]) -> Dict[str, bool]:
        normalized: Dict[str, bool] = {}
        if isinstance(job_enable_flags, dict):
            for name, flag in job_enable_flags.items():
                if isinstance(flag, bool):
                    normalized[str(name)] = flag
        return normalized

    def _job_enabled(self, job_type: str) -> bool:
        if job_type in self._job_enable_flags:
            return bool(self._job_enable_flags[job_type])

        plural_name = f"{job_type}s" if not job_type.endswith("s") else job_type
        return bool(self._job_enable_flags.get(plural_name, True))

    # ------------------------------------------------------------

    async def dispatch(self, job_type: str, ctx, payload: dict):
        if job_type not in self._job_types:
            raise ValueError(f"Unknown job type: {job_type}")

        if not self._job_enabled(job_type):
            log.info(
                f"[{getattr(ctx, 'creator_id', 'unknown')}] Job '{job_type}' "
                "rejected: disabled via config (restart required)"
            )
            return None

        # --------------------------------------------------
        # TIER ENFORCEMENT (AUTHORITATIVE)
        # --------------------------------------------------

        if job_type == "clip":
            max_jobs = ctx.limits.get("max_concurrent_clip_jobs")
            if max_jobs is not None:
                active = self._count_active_jobs(ctx.creator_id, job_type)
                if active >= max_jobs:
                    log.warning(
                        f"[{ctx.creator_id}] Clip job refused "
                        f"(active={active}, limit={max_jobs})"
                    )
                    return None

        # --------------------------------------------------
        # JOB CREATION
        # --------------------------------------------------

        job = self._job_types[job_type](ctx, payload)

        append_job({
            "id": job.id,
            "type": job_type,
            "creator_id": ctx.creator_id,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "updated_at": job.updated_at,
            "payload": payload
        })

        task = asyncio.create_task(self._run_job(job))

        # Attach authoritative metadata for enforcement + visibility
        task._job = job
        task._job_type = job_type
        task._creator_id = ctx.creator_id

        self._active_jobs[job.id] = task

        # Metrics: dispatched
        self._metrics["dispatched"] += 1

        log.info(f"[{ctx.creator_id}] Job queued: {job_type} ({job.id})")
        return job.id

    # ------------------------------------------------------------

    async def _run_job(self, job: Job):
        try:
            job.status = "running"
            job.started_at = int(time.time())
            job.updated_at = job.started_at

            update_job(job.id, {
                "status": "running",
                "started_at": job.started_at,
                "updated_at": job.updated_at
            })

            await job.run()

            job.status = "completed"
            job.completed_at = int(time.time())
            job.updated_at = job.completed_at

            update_job(job.id, {
                "status": "completed",
                "completed_at": job.completed_at,
                "finished_at": job.completed_at,
                "updated_at": job.updated_at
            })

            # Metrics: completed
            self._metrics["completed"] += 1

        except Exception as e:
            job.status = "failed"
            job.completed_at = int(time.time())
            job.updated_at = job.completed_at
            update_job(job.id, {
                "status": "failed",
                "completed_at": job.completed_at,
                "finished_at": job.completed_at,
                "updated_at": job.updated_at,
                "error": str(e)
            })

            # Metrics: failed
            self._metrics["failed"] += 1

            log.exception(f"Job {job.id} failed")

        finally:
            self._active_jobs.pop(job.id, None)
