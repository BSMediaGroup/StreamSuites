"""
Optional file-backed hot reload watcher.

This watcher is intentionally lightweight and disabled by default. When
enabled via system config it monitors a directory (default: runtime/exports)
for content changes and re-publishes runtime snapshot + telemetry exports.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

from core.state_exporter import runtime_snapshot_exporter, runtime_state
from shared.logging.logger import get_logger
from shared.utils.hashing import stable_hash_for_paths

log = get_logger("core.hot_reload")


class HotReloadWatcher:
    def __init__(
        self,
        *,
        watch_path: str = "runtime/exports",
        interval_seconds: float = 5.0,
    ) -> None:
        self.watch_path = Path(watch_path)
        self.interval_seconds = max(1.0, float(interval_seconds or 5.0))
        self._running = False
        self._last_hash: Optional[str] = None

    def _collect_paths(self) -> List[Path]:
        if self.watch_path.is_file():
            return [self.watch_path]

        if not self.watch_path.exists():
            return []

        return [p for p in self.watch_path.rglob("*") if p.is_file()]

    def _compute_hash(self) -> Optional[str]:
        paths = self._collect_paths()
        if not paths:
            return None
        return stable_hash_for_paths(paths)

    async def run(self, stop_event: asyncio.Event) -> None:
        if self._running:
            log.warning("Hot reload watcher already running; ignoring duplicate start")
            return

        self._running = True
        runtime_state.record_event(
            source="hot_reload",
            severity="info",
            message=f"Hot reload watcher started for {self.watch_path}",
        )

        try:
            self._last_hash = self._compute_hash()
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    pass

                if stop_event.is_set():
                    break

                new_hash = self._compute_hash()
                if new_hash is None:
                    log.debug(
                        f"Hot reload watcher found no files under {self.watch_path}; waiting"
                    )
                    continue

                if self._last_hash is None:
                    self._last_hash = new_hash
                    continue

                if new_hash != self._last_hash:
                    runtime_state.record_event(
                        source="hot_reload",
                        severity="info",
                        message=f"Change detected under {self.watch_path}; republishing exports",
                    )
                    try:
                        runtime_snapshot_exporter.publish()
                    except Exception as exc:  # pragma: no cover - defensive
                        runtime_state.record_event(
                            source="hot_reload",
                            severity="error",
                            message=f"Export republish failed: {exc}",
                        )
                        log.warning(f"Hot reload export publish failed: {exc}")

                    self._last_hash = new_hash

        finally:
            self._running = False
            runtime_state.record_event(
                source="hot_reload",
                severity="info",
                message=f"Hot reload watcher stopped for {self.watch_path}",
            )

