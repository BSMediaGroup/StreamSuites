"""
Minimal JSON publisher for public export snapshots.

This writer intentionally avoids dashboard-specific mirroring and is scoped to
static export roots (e.g., exports/public/) for future gallery consumption.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from shared.logging.logger import get_logger

log = get_logger("shared.public_exports.publisher")


class PublicExportPublisher:
    """
    Atomic JSON writer for public export documents.

    This publisher is intentionally minimal: it writes to a configurable base
    directory and does not mirror into dashboard state roots.
    """

    DEFAULT_BASE_DIR = Path("exports/public")

    def __init__(self, *, base_dir: Path | str | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else self.DEFAULT_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _write_atomic(self, target: Path, payload: Any) -> None:
        serialized = json.dumps(payload, indent=2)
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile("w", dir=target.parent, delete=False, encoding="utf-8") as tmp:
            tmp.write(serialized)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = Path(tmp.name)

        temp_path.replace(target)

    def publish(self, relative_path: Path | str, payload: Any) -> Path:
        """
        Write a public export document to the configured base directory.

        Returns the resolved path to the written file to aid observability.
        """
        rel = Path(relative_path)
        target = self._base_dir / rel

        try:
            self._write_atomic(target, payload)
        except Exception as exc:
            log.error(f"Failed to write public export {rel}: {exc}")
            raise

        return target
