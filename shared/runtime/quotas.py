from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Dict, Optional

from shared.storage.state_store import publish_quota_snapshot


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
# Quota Tracker (AUTHORITATIVE)
# ======================================================================

class QuotaTracker:
    """
    Runtime-authoritative quota tracker.

    - Tracks cumulative usage
    - Enforces buffer + hard caps
    - Resets automatically on UTC day rollover
    - Emits dashboard snapshots
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
    # Core operations
    # --------------------------------------------------

    def consume(self, units: int) -> None:
        """
        Consume quota units.

        Raises:
        - QuotaBufferWarning when entering buffer zone
        - QuotaExceeded when hard limit is exceeded
        """
        if units <= 0:
            return

        self.state.reset_if_new_day()

        projected = self.state.used + units

        if projected > self.policy.hard_limit:
            self._publish(status="exhausted")
            raise QuotaExceeded(
                f"Quota exceeded: {projected} / {self.policy.hard_limit}"
            )

        if (
            self.state.used < self.policy.buffer_threshold
            and projected >= self.policy.buffer_threshold
        ):
            self.state.used = projected
            self._publish(status="buffer")
            raise QuotaBufferWarning(
                f"Quota buffer entered: {projected} / {self.policy.hard_limit}"
            )

        self.state.used = projected
        self._publish(status=self._status())

    # --------------------------------------------------
    # Introspection
    # --------------------------------------------------

    def remaining(self) -> int:
        self.state.reset_if_new_day()
        return max(0, self.policy.hard_limit - self.state.used)

    def snapshot(self) -> Dict[str, int]:
        """
        Safe snapshot for dashboards or exporters.
        """
        self.state.reset_if_new_day()
        return {
            "used": self.state.used,
            "remaining": self.remaining(),
            "max": self.policy.hard_limit,
            "buffer": self.policy.buffer_units,
        }

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    def _status(self) -> str:
        if self.state.used >= self.policy.hard_limit:
            return "exhausted"
        if self.state.used >= self.policy.buffer_threshold:
            return "buffer"
        return "ok"

    def _publish(self, status: Optional[str] = None) -> None:
        """
        Publish a quota snapshot for dashboard consumption.
        """
        snap = self.snapshot()
        publish_quota_snapshot({
            "creator_id": self.creator_id,
            "platform": self.platform,
            "date": self.state.day.isoformat(),
            "used": snap["used"],
            "remaining": snap["remaining"],
            "max": snap["max"],
            "buffer": snap["buffer"],
            "status": status or self._status(),
        })


# ======================================================================
# Registry (Shared, In-Memory)
# ======================================================================

class QuotaRegistry:
    """
    Global in-memory registry of quota trackers.

    Keyed by:
    - creator_id
    - platform
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
        policy = QuotaPolicy(
            max_units=max_units,
            buffer_units=buffer_units,
        )
        tracker = QuotaTracker(
            creator_id=creator_id,
            platform=platform,
            policy=policy,
        )
        self._trackers[self._key(creator_id, platform)] = tracker
        return tracker

    def get(
        self,
        *,
        creator_id: str,
        platform: str,
    ) -> Optional[QuotaTracker]:
        return self._trackers.get(self._key(creator_id, platform))


# ======================================================================
# Singleton (Runtime-Authoritative)
# ======================================================================

quota_registry = QuotaRegistry()
