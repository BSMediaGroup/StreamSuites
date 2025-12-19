"""
Dashboard state publisher helpers.

This module centralizes atomic writes of runtime/job snapshots
and optional mirroring into the dashboard hosting directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from shared.logging.logger import get_logger

log = get_logger("shared.state_publisher")


class DashboardStatePublisher:
    """
    Atomic snapshot writer with optional mirroring into the dashboard
    hosting root (e.g., GitHub Pages checkout or bucket mount).
    """

    DEFAULT_BASE_DIR = Path("shared/state")
    ENV_KEYS = (
        "DASHBOARD_STATE_PUBLISH_ROOT",
        "STREAMSUITES_STATE_PUBLISH_ROOT",
    )

    def __init__(
        self,
        base_dir: Path | str | None = None,
        publish_root: Path | str | None = None,
    ):
        self._base_dir = Path(base_dir) if base_dir else self.DEFAULT_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

        env_root = self._get_env_publish_root()
        autodetect_root = self._auto_detect_publish_root()

        self._publish_root = (
            Path(publish_root)
            if publish_root
            else (
                Path(env_root)
                if env_root
                else (Path(autodetect_root) if autodetect_root else None)
            )
        )

        if self._publish_root:
            target = self._publish_root / "shared" / "state"
            target.mkdir(parents=True, exist_ok=True)
            log.info(f"Dashboard state publish root: {target}")

    # ------------------------------------------------------------------
    # Environment helpers
    # ------------------------------------------------------------------

    def _get_env_publish_root(self) -> Optional[str]:
        for key in self.ENV_KEYS:
            val = os.getenv(key)
            if val:
                return val
        return None

    def _auto_detect_publish_root(self) -> Optional[str]:
        """
        Detect a nearby dashboard checkout for default mirroring.

        Common local layout:
            /workspace/StreamSuites
            /workspace/StreamSuites-Dashboard
        """
        candidates = [
            Path("../StreamSuites-Dashboard/docs"),
            Path("../StreamSuites-Dashboard"),
            Path("./StreamSuites-Dashboard/docs"),
            Path("./StreamSuites-Dashboard"),
        ]

        for candidate in candidates:
            if (candidate / "shared" / "state").exists():
                return str(candidate)

        return None

    # ------------------------------------------------------------------
    # Atomic writer
    # ------------------------------------------------------------------

    def _write_atomic(self, path: Path, payload: Any) -> None:
        serialized = json.dumps(payload, indent=2)
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(serialized)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = Path(tmp.name)

        temp_path.replace(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def publish_root(self) -> Optional[Path]:
        return self._publish_root

    def publish(self, relative_path: Path | str, payload: Any) -> None:
        """
        Write snapshot to shared/state/<relative_path> and optionally
        mirror to <publish_root>/shared/state/<relative_path>.
        """
        rel = Path(relative_path)
        target = self._base_dir / rel

        try:
            self._write_atomic(target, payload)
        except Exception as e:
            log.error(f"Failed to write state snapshot {rel}: {e}")
            return

        if not self._publish_root:
            return

        mirror = self._publish_root / "shared" / "state" / rel
        try:
            self._write_atomic(mirror, payload)
        except Exception as e:
            log.warning(f"Failed to mirror snapshot to dashboard root: {e}")

    def mirror_existing(self, relative_path: Path | str) -> bool:
        """
        Mirror an already-written state file into the publish root.
        Useful for cron/deploy hooks where the runtime is not running.
        """
        rel = Path(relative_path)
        source = self._base_dir / rel

        if not source.exists():
            log.warning(f"State file not found for mirroring: {source}")
            return False

        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception as e:
            log.error(f"Failed to load state file for mirroring: {e}")
            return False

        self.publish(rel, payload)
        return True
