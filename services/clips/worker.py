from __future__ import annotations

import asyncio
from typing import Callable, Optional

from shared.logging.logger import get_logger
from services.clips.encoder import ClipEncoder
from services.clips.models import ClipRecord
from services.clips.storage import ClipStore
from services.clips.uploader import RumbleUploader

log = get_logger("services.clips.worker")


class ClipWorkerSupervisor:
    """
    Background worker that processes queued clips with bounded concurrency.
    """

    def __init__(
        self,
        store: ClipStore,
        encoder: ClipEncoder,
        uploader: RumbleUploader,
        *,
        concurrency: int = 2,
        poll_interval: float = 2.0,
        on_state_change: Optional[Callable[[], None]] = None,
    ):
        self._store = store
        self._encoder = encoder
        self._uploader = uploader
        self._concurrency = max(1, concurrency)
        self._poll_interval = poll_interval
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._inflight: set[asyncio.Task] = set()
        self._on_state_change = on_state_change

    async def start(self):
        if self._task:
            return
        log.info(
            f"Clip worker starting (concurrency={self._concurrency}, poll={self._poll_interval}s)"
        )
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._drain_inflight()
        log.info("Clip worker stopped")

    async def _run(self):
        try:
            while not self._stop_event.is_set():
                await self._launch_ready_jobs()
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            log.debug("Clip worker cancelled")
            raise

    async def _launch_ready_jobs(self):
        available_slots = self._concurrency - len(
            [t for t in self._inflight if not t.done()]
        )
        if available_slots <= 0:
            return

        claimed = self._store.claim_queued(available_slots)
        for clip in claimed:
            task = asyncio.create_task(self._process_clip(clip))
            self._inflight.add(task)
            task.add_done_callback(self._inflight.discard)

    async def _process_clip(self, clip: ClipRecord):
        async with self._semaphore:
            clip_id = clip.clip_id
            try:
                self._notify_state()
                output_path = await self._encoder.encode(
                    clip.source_path,
                    clip.start_seconds,
                    clip.duration_seconds,
                    clip.clip_id,
                )
                clip_record = self._store.update_state(
                    clip.clip_id,
                    "encoded",
                    output_path=str(output_path),
                    reason="encoded",
                    job_type="encode",
                )
                self._notify_state()

                self._store.record_job_transition(clip_id, "upload", "uploading", detail="uploading")
                clip_record = self._store.update_state(
                    clip_id,
                    "uploading",
                    reason="uploading",
                    job_type="upload",
                )
                self._notify_state()

                result = await self._uploader.publish(clip_id, output_path)
                clip_record = self._store.update_state(
                    clip_id,
                    "published",
                    published_url=result.published_url,
                    reason=result.detail or "published",
                    job_type="upload",
                )
                self._notify_state()
                final_state = clip_record.state if clip_record else "published"
                log.info(f"[{clip_id}] Clip lifecycle complete ({final_state})")
            except Exception as e:
                log.exception(f"[{clip_id}] Clip processing failed")
                self._store.update_state(
                    clip_id,
                    "failed",
                    reason="failed",
                    error=str(e),
                    job_type="clip",
                )
                self._notify_state()

    async def _drain_inflight(self):
        active = [t for t in self._inflight if not t.done()]
        if not active:
            return
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)

    def _notify_state(self):
        if self._on_state_change:
            try:
                self._on_state_change()
            except Exception:
                log.debug("State change notification failed", exc_info=True)
