"""
StreamSuites Runtime version propagation utility.

This script keeps runtime-owned version identifiers aligned across
runtime metadata and exported JSON files. It optionally updates
adjacent dashboard documentation files (version manifest + About JSON)
when a dashboard checkout is available, but it never introduces runtime
execution dependencies on dashboard assets.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

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
    parser.add_argument(
        "--dashboard-root",
        type=Path,
        default=ROOT.parent / "StreamSuites-Dashboard" / "docs",
        help="Dashboard docs root for optional version/About updates "
             "(default: ../StreamSuites-Dashboard/docs)",
    )
    parser.add_argument(
        "--about-dir",
        type=Path,
        default=None,
        help="Override About JSON directory "
             "(defaults to <dashboard-root>/about)",
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


def update_changelog_sources(version: str) -> bool:
    paths = [
        ROOT / "changelog" / "changelog.runtime.json",
        ROOT / "runtime" / "exports" / "changelog.runtime.json",
    ]

    changed = False

    for path in paths:
        if not path.exists():
            continue

        entries = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    entry["version"] = version

            _write_json(path, entries)
            changed = True

    export_path = ROOT / "runtime" / "exports" / "changelog.json"
    if export_path.exists():
        payload = json.loads(export_path.read_text(encoding="utf-8"))

        if isinstance(payload, dict):
            meta = payload.get("meta")
            if isinstance(meta, dict):
                meta["version"] = version

            entries = payload.get("entries")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        entry["version"] = version

            _write_json(export_path, payload)
            changed = True

    return changed


def _iter_about_files(about_dir: Path) -> Iterable[Path]:
    if not about_dir.exists():
        return []

    return sorted(
        p for p in about_dir.rglob("about*.json") if p.is_file()
    )


def update_about_json(version: str, about_dir: Path) -> bool:
    changed = False

    for path in _iter_about_files(about_dir):
        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            data["version"] = version
            _write_json(path, data)
            changed = True

    return changed


def update_dashboard_version_manifest(
    version: str,
    build: str | None,
    dashboard_root: Path,
) -> bool:
    manifest = dashboard_root / "version.json"
    if not manifest.exists():
        return False

    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False

    data["version"] = version

    if build:
        data["build"] = build

    _write_json(manifest, data)
    return True


def main() -> int:
    args = parse_args()
    about_dir = args.about_dir or (args.dashboard_root / "about")
    version = normalize_version(args.version)

    changed = False

    changed |= update_runtime_version_py(version, args.build)
    changed |= update_changelog_sources(version)
    changed |= update_dashboard_version_manifest(
        version,
        args.build,
        args.dashboard_root,
    )
    changed |= update_about_json(version, about_dir)

    if not changed:
        print("No files updated; verify paths or version changes.")
        return 1

    print("Version stamping complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
