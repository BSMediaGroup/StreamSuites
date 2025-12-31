from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from shared.logging.logger import get_logger

log = get_logger("shared.config.system")

_CONFIG_PATH = Path(__file__).parent / "system.json"


@dataclass
class ClipDestination:
    platform: str
    channel_url: str


@dataclass
class ClipEncodingConfig:
    concurrency: int = 2
    ffmpeg_path: str = r"X:\ffmpeg\bin\ffmpeg.exe"


@dataclass
class ClipExportConfig:
    state_path: str = "shared/state/clips.json"
    interval_seconds: int = 30


@dataclass
class ClipSystemConfig:
    default_destination: ClipDestination
    encoding: ClipEncodingConfig
    export: ClipExportConfig


@dataclass
class SystemSettings:
    platform_polling_enabled: bool = True
    platforms: Dict[str, bool] = field(default_factory=lambda: {
        "youtube": True,
        "twitch": True,
        "discord": True,
    })


@dataclass
class SystemConfig:
    clips: ClipSystemConfig
    system: SystemSettings


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        log.warning(f"system.json not found at {path}; using defaults")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:  # pragma: no cover - defensive
        log.warning(f"Failed to load system.json ({e}); using defaults")
        return {}


def _load_clip_destination(raw: Dict[str, Any]) -> ClipDestination:
    default_url = "https://rumble.com/c/StreamSuites"
    platform = raw.get("platform", "rumble") if isinstance(raw, dict) else "rumble"
    channel_url = raw.get("channel_url", default_url) if isinstance(raw, dict) else default_url
    return ClipDestination(platform=platform, channel_url=channel_url)


def _load_clip_encoding(raw: Optional[Dict[str, Any]]) -> ClipEncodingConfig:
    if not isinstance(raw, dict):
        return ClipEncodingConfig()

    concurrency = raw.get("concurrency", ClipEncodingConfig.concurrency)
    ffmpeg_path = raw.get("ffmpeg_path", ClipEncodingConfig.ffmpeg_path)
    try:
        concurrency_int = int(concurrency)
    except Exception:
        concurrency_int = ClipEncodingConfig.concurrency
    return ClipEncodingConfig(concurrency=concurrency_int, ffmpeg_path=str(ffmpeg_path))


def _load_clip_export(raw: Optional[Dict[str, Any]]) -> ClipExportConfig:
    if not isinstance(raw, dict):
        return ClipExportConfig()

    interval = raw.get("interval_seconds", ClipExportConfig.interval_seconds)
    try:
        interval_int = int(interval)
    except Exception:
        interval_int = ClipExportConfig.interval_seconds

    path = raw.get("state_path", ClipExportConfig.state_path)
    return ClipExportConfig(state_path=str(path), interval_seconds=interval_int)


def _load_system_settings(raw: Optional[Dict[str, Any]]) -> SystemSettings:
    if not isinstance(raw, dict):
        return SystemSettings()

    polling_enabled = raw.get("platform_polling_enabled", SystemSettings.platform_polling_enabled)
    if isinstance(polling_enabled, bool):
        value = polling_enabled
    else:
        log.warning("platform_polling_enabled must be boolean; defaulting to true")
        value = SystemSettings.platform_polling_enabled

    platforms_raw = raw.get("platforms")
    platforms_enabled = {
        "youtube": True,
        "twitch": True,
        "discord": True,
    }

    if isinstance(platforms_raw, dict):
        for name in list(platforms_enabled.keys()):
            entry = platforms_raw.get(name)
            if isinstance(entry, dict):
                flag = entry.get("enabled")
                if isinstance(flag, bool):
                    platforms_enabled[name] = flag
            elif isinstance(entry, bool):
                platforms_enabled[name] = entry

    return SystemSettings(
        platform_polling_enabled=value,
        platforms=platforms_enabled,
    )


def load_system_config(raw: Optional[Dict[str, Any]] = None) -> SystemConfig:
    raw = raw if raw is not None else _load_json(_CONFIG_PATH)

    clips_raw = raw.get("clips", {}) if isinstance(raw, dict) else {}
    default_destination = _load_clip_destination(clips_raw.get("default_destination", {}))
    encoding_cfg = _load_clip_encoding(clips_raw.get("encoding"))
    export_cfg = _load_clip_export(clips_raw.get("export"))

    clip_config = ClipSystemConfig(
        default_destination=default_destination,
        encoding=encoding_cfg,
        export=export_cfg,
    )

    system_raw = raw.get("system", {}) if isinstance(raw, dict) else {}
    system_cfg = _load_system_settings(system_raw)

    return SystemConfig(clips=clip_config, system=system_cfg)
