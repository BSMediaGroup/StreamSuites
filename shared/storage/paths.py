"""
Shared storage path utilities.

This module defines canonical filesystem locations for
persisted runtime state, configuration snapshots, and
future disk-backed artifacts.

Design goals:
- Single source of truth for storage paths
- OS-safe, repo-relative resolution
- Zero side effects beyond directory creation
"""

from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------
# BASE DIRECTORIES
# ----------------------------------------------------------------------

# Repo root is assumed to be the current working directory
# when StreamSuites is launched (consistent with core.app / discord_app)
BASE_DIR = Path.cwd()

STORAGE_DIR = BASE_DIR / "shared" / "storage"
STATE_DIR = STORAGE_DIR / "state"
CACHE_DIR = STORAGE_DIR / "cache"

# Ensure directories exist (safe + idempotent)
STATE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# STATE PATH HELPERS
# ----------------------------------------------------------------------

def get_state_path(name: str) -> Path:
    """
    Return a path inside the shared state directory.

    Example:
        get_state_path("discord/status.json")

    This function DOES NOT write files.
    It only guarantees directory existence.
    """

    path = STATE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_path(name: str) -> Path:
    """
    Return a path inside the shared cache directory.
    """

    path = CACHE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
