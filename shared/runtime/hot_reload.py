"""File-backed hot reload watcher for runtime exports."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.state_exporter import runtime_snapshot_exporter, runtime_state
from shared.logging.logger import get_logger
from shared.utils.hashing import stable_hash_for_paths

log = get_logger("runtime.hot_reload")


@dataclass
class HotReloadConfig:
    enabled: bool = False
    watch_path: str = "runtime/exports"
    interval_seconds: float = 5.0

    @classmethod
    def from_env(cls, *, base: Optional["HotReloadConfig"] = None) -> "HotReloadConfig":
        cfg = base or cls()
        override_flag = os.getenv("STREAMSUITES_HOT_RELOAD")
        if override_flag is not None:
            cfg.enabled = override_flag.lower() in {"1", "true", "yes", "on"}

        watch_override = os.getenv("STREAMSUITES_HOT_RELOAD_PATH")
        if watch_override:
            cfg.watch_path = watch_override

        interval_override = os.getenv("STREAMSUITES_HOT_RELOAD_INTERVAL")
        if interval_override:
            try:
                cfg.interval_seconds = float(interval_override)
            except Exception:
                log.warning(
                    "Invalid STREAMSUITES_HOT_RELOAD_INTERVAL=%s; using %s",  # type: ignore[arg-type]
                    interval_override,
                    cfg.interval_seconds,
                )

        cfg.interval_seconds = max(1.0, float(cfg.interval_seconds or 5.0))
        return cfg


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
        self._last_seen_payloads: Dict[Path, Dict] = {}

    def _target_paths(self) -> List[Path]:
        if self.watch_path.is_file():
            return [self.watch_path]
        if not self.watch_path.exists():
            return []
        return [p for p in self.watch_path.rglob("*.json") if p.is_file()]

    def _compute_hash(self) -> Optional[str]:
        paths = self._target_paths()
        if not paths:
            return None
        return stable_hash_for_paths(paths)

    def _load_changed_files(self, changed: Iterable[Path]) -> List[Tuple[Path, Dict]]:
        loaded: List[Tuple[Path, Dict]] = []
        for path in changed:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    loaded.append((path, data))
                    self._last_seen_payloads[path] = data
            except Exception as exc:
                log.warning(f"Hot reload skipped invalid JSON at {path}: {exc}")
        return loaded

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
                    continue

                if self._last_hash is None:
                    self._last_hash = new_hash
                    continue

                if new_hash != self._last_hash:
                    changed_paths = self._target_paths()
                    loaded = self._load_changed_files(changed_paths)
                    runtime_state.record_event(
                        source="hot_reload",
                        severity="info",
                        message=(
                            f"Detected changes under {self.watch_path}; "
                            f"loaded {len(loaded)} JSON export(s)"
                        ),
                    )
                    runtime_state.record_platform_heartbeat("hot_reload")

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


def build_hot_reload_watcher(config: HotReloadConfig) -> Optional[HotReloadWatcher]:
    if not config.enabled:
        return None
    return HotReloadWatcher(
        watch_path=config.watch_path,
        interval_seconds=config.interval_seconds,
    )


__all__ = [
    "HotReloadWatcher",
    "HotReloadConfig",
    "build_hot_reload_watcher",
]

