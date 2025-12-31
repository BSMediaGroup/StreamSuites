"""
Runtime snapshot exporter.

This module builds a dashboard-compatible runtime snapshot describing platform
status, creator registry state, and heartbeat/error telemetry. It writes
`shared/state/runtime_snapshot.json` (and mirrors into the dashboard publish
root when configured) via DashboardStatePublisher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.logging.logger import get_logger
from shared.storage.state_publisher import DashboardStatePublisher

log = get_logger("core.state_exporter")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_counters() -> Dict[str, int]:
    return {
        "messages": 0,
        "triggers": 0,
        "actions": 0,
        "actions_failed": 0,
    }


@dataclass
class PlatformRuntimeState:
    enabled: bool = False
    telemetry_enabled: bool = False
    active: bool = False
    status: str = "inactive"
    last_heartbeat: Optional[str] = None
    last_success_ts: Optional[str] = None
    last_error: Optional[str] = None
    last_event_ts: Optional[str] = None
    counters: Dict[str, int] = field(default_factory=_default_counters)

    def ensure_counter_keys(self):
        # Keep counters backward-compatible if older snapshots are reloaded
        for key, default in _default_counters().items():
            self.counters.setdefault(key, default)


@dataclass
class CreatorRuntimeState:
    creator_id: str = ""
    display_name: str = ""
    enabled: bool = True
    platforms: Dict[str, bool] = field(default_factory=dict)
    last_heartbeat: Optional[str] = None
    last_error: Optional[str] = None


class RuntimeState:
    """
    In-memory runtime telemetry tracker.

    This class is intentionally simple: it tolerates missing data and never
    raises. State is updated opportunistically by the scheduler and app.
    """

    def __init__(self) -> None:
        self._platforms: Dict[str, PlatformRuntimeState] = {}
        self._creators: Dict[str, CreatorRuntimeState] = {}
        self._rumble_chat: Dict[str, Any] = {}

    # ------------------------------------------------------------
    # Configuration ingestion
    # ------------------------------------------------------------

    def apply_platform_config(self, config: Dict[str, Dict[str, bool]]) -> None:
        for name, cfg in sorted(config.items()):
            current = self._platforms.get(name, PlatformRuntimeState())
            current.enabled = bool(cfg.get("enabled", False))
            current.telemetry_enabled = bool(cfg.get("telemetry_enabled", current.enabled))
            current.active = False  # reset on new config to avoid stale flags
            current.status = "disabled" if not current.enabled else "inactive"
            current.last_error = None
            current.ensure_counter_keys()
            self._platforms[name] = current

    def apply_creators_config(self, creators: List[Dict[str, Any]]) -> None:
        for entry in creators:
            creator_id = entry.get("creator_id")
            if not creator_id:
                continue

            display_name = entry.get("display_name", creator_id)
            enabled = bool(entry.get("enabled", True))
            raw_platforms = entry.get("platforms", {}) or {}

            platforms: Dict[str, bool] = {}
            if isinstance(raw_platforms, dict):
                for name, cfg in raw_platforms.items():
                    if isinstance(cfg, dict):
                        platforms[name] = bool(cfg.get("enabled", cfg.get("active", False) or cfg.get("value", False)))
                    else:
                        platforms[name] = bool(cfg)
            elif isinstance(raw_platforms, list):
                for cfg in raw_platforms:
                    if isinstance(cfg, str):
                        platforms[cfg] = True
                    elif isinstance(cfg, dict):
                        name = cfg.get("name") or cfg.get("platform")
                        if name:
                            platforms[name] = bool(cfg.get("enabled", True))

            self._creators[creator_id] = CreatorRuntimeState(
                creator_id=creator_id,
                display_name=display_name,
                enabled=enabled,
                platforms=platforms,
            )

    # ------------------------------------------------------------
    # Runtime updates
    # ------------------------------------------------------------

    def _get_platform_state(self, platform: str) -> PlatformRuntimeState:
        state = self._platforms.get(platform)
        if not state:
            state = PlatformRuntimeState()
            self._platforms[platform] = state
        state.ensure_counter_keys()
        return state

    def record_platform_status(
        self,
        platform: str,
        status: str,
        *,
        creator_id: Optional[str] = None,
        error: Optional[str] = None,
        success: bool = False,
        last_event: bool = False,
    ) -> None:
        state = self._get_platform_state(platform)
        state.status = status
        if status == "failed":
            state.active = False
        elif status in {"connected", "running"}:
            state.active = True

        if error:
            state.last_error = error
        elif success:
            state.last_error = None

        now = _utc_now_iso()
        if success:
            state.last_success_ts = now
        if last_event:
            state.last_event_ts = now

        self._platforms[platform] = state

        if creator_id and creator_id in self._creators:
            if error:
                self._creators[creator_id].last_error = error
            elif success:
                self._creators[creator_id].last_error = None

    def record_platform_started(self, platform: str, creator_id: Optional[str] = None) -> None:
        self.record_platform_status(platform, "connected", creator_id=creator_id, success=True)

    def record_platform_error(self, platform: str, message: str, creator_id: Optional[str] = None) -> None:
        state = self._get_platform_state(platform)
        state.last_error = message
        state.active = False
        state.status = "failed"
        self._platforms[platform] = state

        if creator_id and creator_id in self._creators:
            self._creators[creator_id].last_error = message

    def record_platform_heartbeat(self, platform: str) -> None:
        state = self._get_platform_state(platform)
        if not state.telemetry_enabled:
            self._platforms[platform] = state
            return
        state.last_heartbeat = _utc_now_iso()
        self._platforms[platform] = state

    def record_creator_heartbeat(self, creator_id: str) -> None:
        state = self._creators.get(creator_id)
        if not state:
            return
        state.last_heartbeat = _utc_now_iso()
        self._creators[creator_id] = state

    def record_creator_error(self, creator_id: str, message: str) -> None:
        state = self._creators.get(creator_id)
        if not state:
            return
        state.last_error = message
        self._creators[creator_id] = state

    def record_platform_event(self, platform: str, creator_id: Optional[str] = None) -> None:
        state = self._get_platform_state(platform)
        state.counters["messages"] = state.counters.get("messages", 0) + 1
        now = _utc_now_iso()
        state.last_event_ts = now
        state.last_success_ts = now
        self._platforms[platform] = state

        if creator_id and creator_id in self._creators:
            # Do not overwrite creator error state here; message receipt implies liveness
            pass

    def record_trigger_actions(
        self,
        platform: str,
        count: int,
        *,
        creator_id: Optional[str] = None,
    ) -> None:
        state = self._get_platform_state(platform)
        state.counters["triggers"] = state.counters.get("triggers", 0) + max(count, 0)
        self._platforms[platform] = state

    def record_action_result(
        self,
        platform: str,
        *,
        success: bool,
        creator_id: Optional[str] = None,
        action_type: Optional[str] = None,
        trigger_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        state = self._get_platform_state(platform)
        key = "actions" if success else "actions_failed"
        state.counters[key] = state.counters.get(key, 0) + 1
        now = _utc_now_iso()
        if success:
            state.last_success_ts = now
            state.last_error = None
        elif error:
            state.last_error = error
        self._platforms[platform] = state

        if creator_id and creator_id in self._creators and error:
            self._creators[creator_id].last_error = error

    # ------------------------------------------------------------
    # Rumble chat ingest status
    # ------------------------------------------------------------

    def record_rumble_chat_status(
        self,
        *,
        chat_id: Optional[str],
        status: str,
        error: Optional[str] = None,
    ) -> None:
        self._rumble_chat = {
            "chat_id": chat_id,
            "ingest_status": status,
            "error": error,
            "updated_at": _utc_now_iso(),
        }

    # ------------------------------------------------------------
    # Snapshot build
    # ------------------------------------------------------------

    @staticmethod
    def _platform_status(state: PlatformRuntimeState) -> str:
        if not state.enabled:
            return "disabled"
        if state.last_error and state.status == "failed":
            return "error"
        if state.active:
            return "running"
        return state.status or "inactive"

    def build_snapshot(self) -> Dict[str, Any]:
        platforms_out: List[Dict[str, Any]] = []
        for name in sorted(self._platforms.keys()):
            state = self._platforms[name]
            state.ensure_counter_keys()
            platforms_out.append({
                "platform": name,
                "enabled": state.enabled,
                "telemetry_enabled": state.telemetry_enabled,
                "status": self._platform_status(state),
                "last_heartbeat": state.last_heartbeat,
                "last_success_ts": state.last_success_ts,
                "last_event_ts": state.last_event_ts,
                "error": state.last_error,
                "counters": dict(state.counters),
            })

        creators_out: List[Dict[str, Any]] = []
        for creator_id in sorted(self._creators.keys()):
            state = self._creators[creator_id]
            creators_out.append({
                "creator_id": state.creator_id,
                "display_name": state.display_name,
                "enabled": state.enabled,
                "platforms": state.platforms,
                "last_heartbeat": state.last_heartbeat,
                "error": state.last_error,
            })

        rumble_chat_out = dict(self._rumble_chat) if self._rumble_chat else None

        return {
            "schema_version": "v1",
            "generated_at": _utc_now_iso(),
            "platforms": platforms_out,
            "creators": creators_out,
            "rumble_chat": rumble_chat_out,
        }


class RuntimeSnapshotExporter:
    """
    Writes runtime_snapshot.json using DashboardStatePublisher.
    """

    DEFAULT_RELATIVE_PATH = "runtime_snapshot.json"

    def __init__(
        self,
        *,
        base_dir: str = "shared/state",
        publish_root: Optional[str] = None,
        state: Optional[RuntimeState] = None,
    ) -> None:
        self._publisher = DashboardStatePublisher(base_dir=base_dir, publish_root=publish_root)
        self._state = state or RuntimeState()

    @property
    def state(self) -> RuntimeState:
        return self._state

    def publish(self) -> Dict[str, Any]:
        payload = self._state.build_snapshot()
        try:
            self._publisher.publish(self.DEFAULT_RELATIVE_PATH, payload)
        except Exception as e:
            log.warning(f"Failed to publish runtime snapshot: {e}")
        return payload


# Shared instances for scheduler/app
runtime_state = RuntimeState()
runtime_snapshot_exporter = RuntimeSnapshotExporter(state=runtime_state)
