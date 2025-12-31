"""Hashing helpers for restart-intent detection."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

from shared.logging.logger import get_logger

log = get_logger("shared.utils.hashing")


def stable_hash_for_paths(paths: Iterable[Path]) -> Optional[str]:
    """Compute a deterministic hash for a collection of files.

    Missing files contribute a placeholder token so that later creation of the
    file is detected as a change. Returns ``None`` when all files are missing.
    """

    digest = hashlib.sha256()
    seen = False

    for path in paths:
        digest.update(str(path).encode("utf-8"))
        try:
            if path.exists():
                seen = True
                digest.update(path.read_bytes())
            else:
                digest.update(b"<missing>")
        except Exception as exc:  # pragma: no cover - defensive logging
            log.warning(f"Failed to hash path {path}: {exc}")
            digest.update(f"<error:{exc}>".encode("utf-8"))

    if not seen:
        return None

    return digest.hexdigest()
