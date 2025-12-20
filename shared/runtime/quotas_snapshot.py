# StreamSuites/shared/runtime/quotas_snapshot.py
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.storage.state_publisher import DashboardStatePublisher
from shared.runtime.quotas import quota_registry, QuotaTracker

log = get_logger("shared.runtime.quotas_snapshot")


# ======================================================================
# Quota Snapshot Exporter (Runtime → shared/state/quotas.json)
#
# Authoritative runtime exporter:
# - Builds ONE document snapshot for all tracked quotas
# - Writes atomically via DashboardStatePublisher
# - Optional mirroring into dashboard publish root if configured
#
# Output file (runtime repo):
#   StreamSuites/shared/state/quotas.json
#
# Schema target (dashboard repo):
#   StreamSuites-Dashboard/schemas/quotas.schema.json
# ======================================================================


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _utc_midnight_next_day(dt: datetime) -> datetime:
  next_day = (dt + timedelta(days=1)).date()
  return datetime(next_day.year, next_day.month, next_day.day, tzinfo=timezone.utc)


def _compute_status(used: int, hard_limit: int, buffer_units: int) -> str:
  """
  Status is derived deterministically:
    - exhausted: used >= hard_limit
    - buffer: used >= (hard_limit - buffer_units)
    - ok: otherwise
  """
  if hard_limit <= 0:
    return "ok"

  if used >= hard_limit:
    return "exhausted"

  threshold = max(0, hard_limit - max(0, buffer_units))
  if used >= threshold:
    return "buffer"

  return "ok"


def _tracker_to_entries(tracker: QuotaTracker) -> List[Dict[str, Any]]:
  """
  Convert one QuotaTracker into schema-aligned entries.

  Current scope:
  - daily window only (authoritative for current design)

  Future:
  - per_minute windows can be added once there is real data
  """
  # Ensure day rollover is respected before snapshot
  tracker.state.reset_if_new_day()

  snap = tracker.snapshot()
  used = int(snap.get("used", 0))
  remaining = int(snap.get("remaining", 0))
  hard_limit = int(snap.get("max", 0))
  buffer_units = int(snap.get("buffer", 0))

  now = _utc_now()

  entry_daily: Dict[str, Any] = {
    "platform": tracker.platform,
    "scope": "creator",
    "creator_id": tracker.creator_id,
    "window": "daily",
    "used": used,
    "max": hard_limit,
    "remaining": remaining,
    "reset_at": _utc_midnight_next_day(now).isoformat().replace("+00:00", "Z"),
    "status": _compute_status(used, hard_limit, buffer_units),
  }

  return [entry_daily]


class QuotaSnapshotPublisher:
  """
  Single writer for quotas.json.

  Writes:
    shared/state/quotas.json

  This is intentionally "clean once":
  - no hacks
  - no partial writes
  - one JSON document per publish
  """

  DEFAULT_RELATIVE_PATH = "quotas.json"

  def __init__(
    self,
    *,
    base_dir: str = "shared/state",
    publish_root: Optional[str] = None,
  ):
    # Note: DashboardStatePublisher expects base_dir to be the directory
    # that contains the state files (e.g. shared/state)
    self._publisher = DashboardStatePublisher(base_dir=base_dir, publish_root=publish_root)

  def build_snapshot(self) -> Dict[str, Any]:
    """
    Build the quotas.json document.

    Shape:
    {
      "schema_version": "v1",
      "generated_at": "...Z",
      "platforms": [ ...entries... ]
    }
    """
    entries: List[Dict[str, Any]] = []

    # quota_registry stores trackers keyed by "creator:platform"
    trackers = getattr(quota_registry, "_trackers", {})
    if isinstance(trackers, dict):
      for tracker in trackers.values():
        if isinstance(tracker, QuotaTracker):
          try:
            entries.extend(_tracker_to_entries(tracker))
          except Exception as e:
            log.warning(f"Quota tracker snapshot failed: {e}")

    doc: Dict[str, Any] = {
      "schema_version": "v1",
      "generated_at": _utc_now().isoformat().replace("+00:00", "Z"),
      "platforms": entries,
    }
    return doc

  def publish(self) -> Dict[str, Any]:
    """
    Publish a full quotas.json snapshot atomically.
    Returns the published document (useful for logging/tests).
    """
    payload = self.build_snapshot()

    # Atomic write to shared/state/quotas.json (and mirror if configured)
    self._publisher.publish(self.DEFAULT_RELATIVE_PATH, payload)

    return payload


# ======================================================================
# Convenience singleton + helper
# ======================================================================

quota_snapshot_publisher = QuotaSnapshotPublisher()


def publish_quota_snapshot_document() -> Dict[str, Any]:
  """
  Public helper used by runtime cadence hooks.

  This intentionally writes ONE document for all quotas.
  """
  return quota_snapshot_publisher.publish()
