"""Runtime-facing admin contract for desktop control surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.config_loader import ConfigLoader
from shared.utils.hashing import stable_hash_for_paths
_SECTION_PATHS: Dict[str, Path] = {
    "system": ConfigLoader.ADMIN_SYSTEM_PATH,
    "creators": ConfigLoader.ADMIN_CREATORS_PATH,
    "triggers": ConfigLoader.ADMIN_TRIGGERS_PATH,
}
_BASELINE_PATHS: Dict[str, Path] = {
    "system": ConfigLoader.SYSTEM_PATH,
    "creators": ConfigLoader.CREATORS_PATH,
    "triggers": ConfigLoader.TRIGGERS_PATH,
}


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2)
    path.write_text(serialized, encoding="utf-8")
    return path


def read_state() -> Dict[str, Any]:
    """Read the latest runtime snapshot for desktop clients."""

    candidates = [
        Path("shared/state/runtime_snapshot.json"),
        Path("runtime/exports/runtime_snapshot.json"),
    ]

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def write_config(section: str, payload: Any) -> Path:
    """
    Write a config override scoped to runtime/admin/<section>.json.

    Only known sections are permitted to enforce runtime write boundaries.
    """

    if section not in _SECTION_PATHS:
        raise ValueError(f"Unsupported admin section: {section}")

    path = _SECTION_PATHS[section]
    return _write_json(path, payload)


def restart_required_sections() -> List[str]:
    """
    Identify config sections that differ from their baseline and require restart.
    """

    pending: List[str] = []

    for section, admin_path in _SECTION_PATHS.items():
        baseline_path = _BASELINE_PATHS.get(section)
        baseline_hash = (
            stable_hash_for_paths([baseline_path]) if baseline_path and baseline_path.exists() else None
        )
        override_hash = stable_hash_for_paths([admin_path]) if admin_path.exists() else None

        if override_hash and override_hash != baseline_hash:
            pending.append(section)

    return pending


__all__ = ["read_state", "write_config", "restart_required_sections"]

