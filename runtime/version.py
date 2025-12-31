"""Runtime version metadata for StreamSuites.

This module is import-safe and exposes authoritative version identifiers for
other runtime modules without executing side effects on import.
"""

from __future__ import annotations

PROJECT_NAME = "StreamSuites™ Runtime"
VERSION = "v0.2.1-alpha"
BUILD = "2025.02"
OWNER = "Daniel Clancy"
COPYRIGHT = "© 2026 Brainstream Media Group"
LICENSE = "Proprietary"

__all__ = [
    "PROJECT_NAME",
    "VERSION",
    "BUILD",
    "OWNER",
    "COPYRIGHT",
    "LICENSE",
    "as_dict",
    "as_string",
]


def as_dict() -> dict[str, str]:
    """Return version metadata as a dictionary."""

    return {
        "project": PROJECT_NAME,
        "version": VERSION,
        "build": BUILD,
        "owner": OWNER,
        "copyright": COPYRIGHT,
        "license": LICENSE,
    }


def as_string() -> str:
    """Return a concise version string."""

    return f"{PROJECT_NAME} {VERSION} (Build {BUILD})"
