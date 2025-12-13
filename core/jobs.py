import asyncio
import uuid
import time
from typing import Dict, Type

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

        append_job({
            "id": job.id,
            "type": job_type,
            "creator_id": ctx.creator_id,
            "status": job.status,
            "created_at": job.created_at,
            "payload": payload
        })

        task = asyncio.create_task(self._run_job(job))
        self._active_jobs[job.id] = task

        log.info(f"[{ctx.creator_id}] Job queued: {job_type} ({job.id})")
        return job.id

    async def _run_job(self, job: Job):
        try:
            job.status = "running"
            update_job(job.id, {"status": "running"})
            await job.run()
            job.status = "completed"
            update_job(job.id, {"status": "completed"})
        except Exception as e:
            job.status = "failed"
            update_job(job.id, {
                "status": "failed",
                "error": str(e)
            })
            log.exception(f"Job {job.id} failed")
        finally:
            self._active_jobs.pop(job.id, None)
