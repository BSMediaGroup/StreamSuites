from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Dict, Optional, List

from shared.storage.state_store import (
    publish_quota_snapshot,                # legacy / transitional
    publish_quota_snapshot_payload,        # authoritative
)


# ======================================================================
# Exceptions
# ======================================================================

class QuotaExceeded(RuntimeError):
    """Raised when a hard quota limit has been exceeded."""


class QuotaBufferWarning(RuntimeError):
    """
    Raised when usage enters the configured buffer zone.
    This is NOT fatal, but should surface as a warning.
    """


# ======================================================================
# Data Models
# ======================================================================

@dataclass
class DailyQuota:
    """
    Tracks cumulative usage for a single UTC day.
    """
    day: date
    used: int = 0

    def reset_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self.day != today:
            self.day = today
            self.used = 0


@dataclass
class QuotaPolicy:
    """
    Declarative quota limits.
    """
    max_units: int
    buffer_units: int

    @property
    def hard_limit(self) -> int:
        return self.max_units

    @property
    def buffer_threshold(self) -> int:
        return max(0, self.max_units - self.buffer_units)


# ======================================================================
# Quota Tracker (ENFORCEMENT ONLY)
# ======================================================================

class QuotaTracker:
    """
    Runtime quota tracker.

    - Tracks cumulative usage
    - Enforces buffer + hard caps
    - Resets automatically on UTC day rollover
    - Does NOT write files
    """

    def __init__(
        self,
        *,
        creator_id: str,
        platform: str,
        policy: QuotaPolicy,
    ):
        self.creator_id = creator_id
        self.platform = platform
        self.policy = policy
        self.state = DailyQuota(
            day=datetime.now(timezone.utc).date(),
            used=0,
        )

    # --------------------------------------------------

    def consume(self, units: int) -> None:
        if units <= 0:
            return

        self.state.reset_if_new_day()
        projected = self.state.used + units

        if projected > self.policy.hard_limit:
            raise QuotaExceeded(
                f"Quota exceeded: {projected} / {self.policy.hard_limit}"
            )

        if (
            self.state.used < self.policy.buffer_threshold
            and projected >= self.policy.buffer_threshold
        ):
            self.state.used = projected
            raise QuotaBufferWarning(
                f"Quota buffer entered: {projected} / {self.policy.hard_limit}"
            )

        self.state.used = projected

    # --------------------------------------------------

    def snapshot(self) -> Dict[str, int]:
        self.state.reset_if_new_day()
        return {
            "used": self.state.used,
            "remaining": max(0, self.policy.hard_limit - self.state.used),
            "max": self.policy.hard_limit,
            "buffer": self.policy.buffer_units,
        }

    def status(self) -> str:
        if self.state.used >= self.policy.hard_limit:
            return "exhausted"
        if self.state.used >= self.policy.buffer_threshold:
            return "buffer"
        return "ok"


# ======================================================================
# Registry (AUTHORITATIVE IN-MEMORY)
# ======================================================================

class QuotaRegistry:
    """
    Global registry of quota trackers.
    """

    def __init__(self):
        self._trackers: Dict[str, QuotaTracker] = {}

    def _key(self, creator_id: str, platform: str) -> str:
        return f"{creator_id}:{platform}"

    def register(
        self,
        *,
        creator_id: str,
        platform: str,
        max_units: int,
        buffer_units: int,
    ) -> QuotaTracker:
        tracker = QuotaTracker(
            creator_id=creator_id,
            platform=platform,
            policy=QuotaPolicy(
                max_units=max_units,
                buffer_units=buffer_units,
            ),
        )
        self._trackers[self._key(creator_id, platform)] = tracker
        return tracker

    def all(self) -> List[QuotaTracker]:
        return list(self._trackers.values())


quota_registry = QuotaRegistry()


# ======================================================================
# Snapshot Aggregator (AUTHORITATIVE SINGLE WRITER)
# ======================================================================

class QuotaSnapshotAggregator:
    """
    Collects all quota trackers and emits a single
    schema-compliant quota snapshot.
    """

    def publish(self) -> None:
        records: List[Dict[str, object]] = []

        for tracker in quota_registry.all():
            snap = tracker.snapshot()

            records.append({
                "platform": tracker.platform,
                "scope": "creator",
                "window": "daily",
                "used": snap["used"],
                "max": snap["max"],
                "remaining": snap["remaining"],
                "reset_at": (
                    datetime.now(timezone.utc)
                    .replace(hour=0, minute=0, second=0, microsecond=0)
                    .isoformat()
                ),
                "status": tracker.status(),
            })

        payload = {
            "schema_version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platforms": records,
        }

        publish_quota_snapshot_payload(payload)


quota_snapshot_aggregator = QuotaSnapshotAggregator()
