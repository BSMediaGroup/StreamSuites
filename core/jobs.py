import asyncio
import uuid
from typing import Dict, Type

from shared.logging.logger import get_logger

log = get_logger("core.jobs")


class Job:
    def __init__(self, ctx, payload: dict):
        self.id = str(uuid.uuid4())
        self.ctx = ctx
        self.payload = payload
        self.status = "pending"

    async def run(self):
        raise NotImplementedError


class JobRegistry:
    def __init__(self):
        self._job_types: Dict[str, Type[Job]] = {}
        self._active_jobs: Dict[str, asyncio.Task] = {}

    def register(self, name: str, job_cls: Type[Job]):
        self._job_types[name] = job_cls
        log.info(f"Registered job type: {name}")

    async def dispatch(self, job_type: str, ctx, payload: dict):
        if job_type not in self._job_types:
            raise ValueError(f"Unknown job type: {job_type}")

        job = self._job_types[job_type](ctx, payload)

        task = asyncio.create_task(self._run_job(job))
        self._active_jobs[job.id] = task

        log.info(f"[{ctx.creator_id}] Job queued: {job_type} ({job.id})")
        return job.id

    async def _run_job(self, job: Job):
        try:
            job.status = "running"
            await job.run()
            job.status = "completed"
        except Exception as e:
            job.status = "failed"
            log.exception(f"Job {job.id} failed: {e}")
        finally:
            self._active_jobs.pop(job.id, None)
