"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.1-alpha (Build 2025.02)
Owner: Daniel Clancy
 Copyright © 2026 Brainstream Media Group
======================================================================
"""

"""
Utility script to mirror runtime/job snapshots into the dashboard
hosting root (GitHub Pages checkout or bucket mount).

Usage:
    python scripts/publish_state.py --target ../StreamSuites-Dashboard/docs

If --target is omitted, the script falls back to the first set environment
variable in:
- DASHBOARD_STATE_PUBLISH_ROOT
- STREAMSUITES_STATE_PUBLISH_ROOT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared.storage.state_publisher import DashboardStatePublisher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish dashboard state JSON")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("shared/state"),
        help="Directory containing state snapshots (default: shared/state)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Dashboard hosting root (will write under shared/state/...)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=["discord/runtime.json", "jobs.json"],
        help="Relative state files to publish",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    publisher = DashboardStatePublisher(
        base_dir=args.base_dir,
        publish_root=args.target,
    )

    if not publisher.publish_root:
        print(
            "No publish root configured; set --target or DASHBOARD_STATE_PUBLISH_ROOT.",
            file=sys.stderr,
        )
        return 1

    ok = True
    for rel in args.files:
        if not publisher.mirror_existing(rel):
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
