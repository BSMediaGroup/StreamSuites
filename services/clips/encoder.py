from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from shared.logging.logger import get_logger

log = get_logger("services.clips.encoder")


class ClipEncoder:
    def __init__(self, ffmpeg_path: str, output_dir: Path | str = "clips/output"):
        self._ffmpeg_path = ffmpeg_path
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def ffmpeg_path(self) -> str:
        # Prefer configured path; fall back to system ffmpeg if missing
        configured = Path(self._ffmpeg_path)
        if configured.exists():
            return str(configured)
        log.warning(f"Configured ffmpeg not found at {configured}; falling back to PATH")
        return "ffmpeg"

    def output_path_for(self, clip_id: str) -> Path:
        return self._output_dir / f"{clip_id}.mp4"

    async def encode(
        self,
        source_path: str,
        start_seconds: float,
        duration_seconds: float,
        clip_id: str,
    ) -> Path:
        """
        Encode a clip using ffmpeg with deterministic output naming.
        """
        output_path = self.output_path_for(clip_id)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss",
            str(start_seconds),
            "-i",
            str(source_path),
            "-t",
            str(duration_seconds),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        log.info(f"[{clip_id}] ffmpeg encode starting: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="ignore")
            stdout_text = stdout.decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"ffmpeg failed (code={process.returncode}) "
                f"stdout={stdout_text} stderr={stderr_text}"
            )

        log.info(f"[{clip_id}] ffmpeg encode complete: {output_path}")
        return output_path
