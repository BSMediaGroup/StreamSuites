# StreamSuites/shared/runtime/scoreboards_snapshot.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.scoreboards.snapshot import ScoreboardEntry, ScoreboardSnapshotBuilder
from shared.storage.state_publisher import DashboardStatePublisher

log = get_logger("shared.runtime.scoreboards_snapshot")


# ======================================================================
# Scoreboard Snapshot Exporter (Runtime → shared/state/scoreboards/...)
#
# Authoritative runtime exporter (creator scoped):
# - Builds ONE document snapshot per creator
# - Writes atomically via DashboardStatePublisher
# - Optional mirroring into dashboard publish root if configured
#
# Output file (runtime repo):
#   StreamSuites/shared/state/scoreboards/snapshots/<creator>.json
#
# Schema target (dashboard repo):
#   StreamSuites-Dashboard/schemas/scoreboards.schema.json (conceptual)
# ======================================================================


class ScoreboardSnapshotPublisher:
  """
  Single writer for scoreboard snapshots per creator.

  This publisher does not compute scores; it serializes provided entries into
  the scoreboard schema shape and writes them atomically.
  """

  DEFAULT_RELATIVE_ROOT = "scoreboards/snapshots"

  def __init__(
    self,
    *,
    base_dir: str = "shared/state",
    publish_root: Optional[str] = None,
    schema_version: str = "v1",
  ) -> None:
    self._publisher = DashboardStatePublisher(base_dir=base_dir, publish_root=publish_root)
    self._builder = ScoreboardSnapshotBuilder(schema_version=schema_version)

  def build_snapshot(
    self,
    *,
    creator_id: str,
    entries: Optional[List[ScoreboardEntry]] = None,
    period: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> Dict[str, Any]:
    """
    Build a scoreboard snapshot document without persisting it.
    """
    return self._builder.build(
      creator_id=creator_id,
      entries=entries or [],
      period=period,
      metadata=metadata,
    )

  def publish(
    self,
    *,
    creator_id: str,
    entries: Optional[List[ScoreboardEntry]] = None,
    period: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> Dict[str, Any]:
    """
    Publish a creator-scoped scoreboard snapshot atomically.

    In the current scaffolding, entries are expected to be pre-computed or
    placeholders provided by upstream modules.
    """
    payload = self.build_snapshot(
      creator_id=creator_id,
      entries=entries,
      period=period,
      metadata=metadata,
    )

    relative_path = f"{self.DEFAULT_RELATIVE_ROOT}/{creator_id}.json"

    try:
      self._publisher.publish(relative_path, payload)
    except Exception as e:
      log.warning(f"Scoreboard snapshot publish failed for {creator_id}: {e}")

    return payload


# ======================================================================
# Convenience singleton + helper
# ======================================================================

scoreboard_snapshot_publisher = ScoreboardSnapshotPublisher()


def publish_scoreboard_snapshot_document(
  *,
  creator_id: str,
  entries: Optional[List[ScoreboardEntry]] = None,
  period: Optional[Dict[str, Any]] = None,
  metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
  """
  Public helper for runtime cadence hooks.
  """
  return scoreboard_snapshot_publisher.publish(
    creator_id=creator_id,
    entries=entries,
    period=period,
    metadata=metadata,
  )
