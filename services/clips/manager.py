from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from shared.config.system import load_system_config
from shared.logging.logger import get_logger
from services.clips.encoder import ClipEncoder
from services.clips.exporter import ClipStateExporter
from services.clips.models import ClipDestination, ClipRecord, ClipRequest
from services.clips.storage import ClipStore
from services.clips.uploader import RumbleUploader
from services.clips.worker import ClipWorkerSupervisor

log = get_logger("services.clips.manager")


class ClipManager:
    """
    Facade for clip ingestion, encoding, upload, and snapshot export.
    """

    def __init__(self):
        self._system_config = load_system_config()
        clip_cfg = self._system_config.clips
        self._store = ClipStore()
        self._encoder = ClipEncoder(
            clip_cfg.encoding.ffmpeg_path,
            output_dir=Path("clips/output"),
        )
        self._uploader = RumbleUploader(channel_url=clip_cfg.default_destination.channel_url)
        self._exporter = ClipStateExporter(state_path=clip_cfg.export.state_path)
        self._worker = ClipWorkerSupervisor(
            self._store,
            self._encoder,
            self._uploader,
            concurrency=clip_cfg.encoding.concurrency,
            poll_interval=2.0,
            on_state_change=self.export_snapshot,
        )
        self._export_interval = clip_cfg.export.interval_seconds
        self._export_task: Optional[asyncio.Task] = None
        self._started = False

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    async def start(self):
        if self._started:
            return
        await self._worker.start()
        self._export_task = asyncio.create_task(self._export_loop())
        self._started = True
        log.info("Clip manager started")

    async def shutdown(self):
        if not self._started:
            return
        await self._worker.stop()
        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass
        self._started = False
        log.info("Clip manager stopped")

    # ------------------------------------------------------------------
    # EXTERNAL API
    # ------------------------------------------------------------------

    def enqueue_clip(self, request: ClipRequest) -> ClipRecord:
        destination = request.destination_override or self._system_config.clips.default_destination
        record = self._store.enqueue(request, destination)
        self.export_snapshot()
        log.info(f"[{record.clip_id}] Clip queued for {record.destination_platform}")
        return record

    def export_snapshot(self) -> None:
        clips = self._store.get_all()
        self._exporter.publish(clips)

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    async def _export_loop(self):
        try:
            while True:
                await asyncio.sleep(self._export_interval)
                self.export_snapshot()
        except asyncio.CancelledError:
            return


# Singleton for runtime consumption
clip_manager = ClipManager()
