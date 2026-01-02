"""Chat event readers and replay metadata helpers.

These helpers intentionally operate in a read-only manner so they can be used
by runtime snapshot generation without impacting live ingestion. The
implementation focuses on deterministic outputs, ordering guarantees, and
filtering of malformed events to keep OBS overlays safe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from shared.logging.logger import get_logger

log = get_logger("shared.chat_events.reader")

# Canonical locations for replay inputs. These are intentionally rooted in the
# repo so snapshot builders can derive replay availability without guessing.
CHAT_LOG_ROOT = Path("shared/state/chat_logs")
CHAT_EVENT_STORAGE_ROOT = Path("shared/storage/chat_events")


@dataclass
class ReplayMetadata:
    available: bool
    platforms: List[str]
    event_count: int
    last_event_timestamp: Optional[str]
    overlay_safe: bool


class _ReplayEvent:
    def __init__(self, *, platform: Optional[str], timestamp: datetime, iso: str) -> None:
        self.platform = platform
        self.timestamp = timestamp
        self.iso = iso

    def sort_key(self) -> Tuple[datetime, str]:
        return (self.timestamp, self.platform or "")


def _parse_iso8601(value: str) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _platform_from_path(path: Path) -> Optional[str]:
    for part in path.parts:
        lowered = part.lower()
        if lowered in {"youtube", "twitch", "kick", "rumble", "pilled"}:
            return lowered
    return None


def _load_json_events(payload: object) -> List[dict]:
    if isinstance(payload, list):
        return [evt for evt in payload if isinstance(evt, dict)]
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list):
            return [evt for evt in events if isinstance(evt, dict)]
    return []


def _iter_event_files(directories: Sequence[Path]) -> Iterable[Path]:
    for base in directories:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            if path.is_file():
                yield path
        for path in sorted(base.rglob("*.ndjson")):
            if path.is_file():
                yield path


def _load_events_from_file(path: Path) -> Tuple[List[_ReplayEvent], bool, int]:
    overlay_safe = True
    parsed_events: List[_ReplayEvent] = []
    total_seen = 0

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        log.warning(f"Failed to read chat replay file {path}: {exc}")
        return [], False, 0

    candidates: List[dict] = []
    if path.suffix == ".ndjson":
        for line in text.splitlines():
            if not line.strip():
                continue
            total_seen += 1
            try:
                loaded = json.loads(line)
                if isinstance(loaded, dict):
                    candidates.append(loaded)
                else:
                    overlay_safe = False
            except json.JSONDecodeError:
                overlay_safe = False
                continue
    else:
        try:
            loaded = json.loads(text)
            extracted = _load_json_events(loaded)
            total_seen = len(extracted)
            candidates.extend(extracted)
        except json.JSONDecodeError:
            log.warning(f"Invalid JSON in replay file {path}")
            return [], False, 0

    platform_hint = _platform_from_path(path)

    for candidate in candidates:
        ts_value = candidate.get("timestamp") or candidate.get("message_at") or candidate.get("received_at")
        ts = _parse_iso8601(ts_value) if ts_value else None
        if not ts:
            overlay_safe = False
            continue

        platform = candidate.get("platform") or platform_hint
        platform_normalized = platform.lower() if isinstance(platform, str) else None

        parsed_events.append(
            _ReplayEvent(
                platform=platform_normalized,
                timestamp=ts,
                iso=ts.isoformat().replace("+00:00", "Z"),
            )
        )

    # Overlay is unsafe if any malformed events were dropped
    if total_seen and len(parsed_events) != total_seen:
        overlay_safe = False

    parsed_events.sort(key=lambda evt: evt.sort_key())
    return parsed_events, overlay_safe, total_seen


def build_replay_metadata() -> ReplayMetadata:
    overlay_safe = True
    events: List[_ReplayEvent] = []

    for path in _iter_event_files([CHAT_LOG_ROOT, CHAT_EVENT_STORAGE_ROOT]):
        parsed, file_safe, _ = _load_events_from_file(path)
        overlay_safe = overlay_safe and file_safe
        events.extend(parsed)

    events.sort(key=lambda evt: evt.sort_key())

    platforms = sorted({evt.platform for evt in events if evt.platform})
    event_count = len(events)
    last_timestamp = events[-1].iso if events else None

    available = event_count > 0
    overlay_safe = overlay_safe and available

    return ReplayMetadata(
        available=available,
        platforms=platforms,
        event_count=event_count,
        last_event_timestamp=last_timestamp,
        overlay_safe=overlay_safe,
    )


__all__ = [
    "ReplayMetadata",
    "build_replay_metadata",
    "CHAT_LOG_ROOT",
    "CHAT_EVENT_STORAGE_ROOT",
]
