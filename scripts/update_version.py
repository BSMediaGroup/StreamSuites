"""
StreamSuites Runtime version propagation utility.

This script keeps runtime-owned version identifiers aligned across
runtime metadata and exported JSON files. It never writes version/build
data outside of the runtime repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update StreamSuites runtime version metadata"
    )
    parser.add_argument(
        "version",
        help="Version string to stamp (e.g., 0.2.3-alpha)",
    )
    parser.add_argument(
        "--build",
        help="Optional build identifier to stamp (e.g., 2026.01.06+004)",
    )
    return parser.parse_args()


def normalize_version(value: str) -> str:
    normalized = value.strip()

    if normalized.startswith("Version "):
        normalized = normalized[len("Version "):]

    if normalized.startswith("v"):
        normalized = normalized[1:]

    return normalized


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def update_runtime_version_py(version: str, build: str | None) -> bool:
    target = ROOT / "runtime" / "version.py"
    original = target.read_text(encoding="utf-8")

    updated = re.sub(
        r'^VERSION = ".*"$',
        f'VERSION = "{version}"',
        original,
        flags=re.MULTILINE,
    )

    if build:
        updated = re.sub(
            r'^BUILD = ".*"$',
            f'BUILD = "{build}"',
            updated,
            flags=re.MULTILINE,
        )

    if updated != original:
        target.write_text(updated, encoding="utf-8")
        return True

    return False


def load_runtime_version_module():
    module_path = ROOT / "runtime" / "version.py"
    spec = importlib.util.spec_from_file_location(
        "streamsuites_runtime_version",
        module_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load runtime version module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def update_runtime_version_export() -> bool:
    version_module = load_runtime_version_module()
    export_path = ROOT / "runtime" / "exports" / "version.json"
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "project": "StreamSuites™",
        "version": version_module.VERSION,
        "build": version_module.BUILD,
        "generated_at": generated_at,
        "source": "runtime",
    }
    _write_json(export_path, payload)
    return True


def main() -> int:
    args = parse_args()
    version = normalize_version(args.version)

    changed = False

    changed |= update_runtime_version_py(version, args.build)
    changed |= update_runtime_version_export()

    if not changed:
        print("No files updated; verify paths or version changes.")
        return 1

    print("Version stamping complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
