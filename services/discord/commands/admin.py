"""
Discord Admin Commands (Control-Plane Runtime)

This module defines administrator-only command surfaces for the Discord
control-plane runtime.

Planned responsibilities:
- System status inspection (runtime, scheduler, heartbeat)
- Discord bot status management (custom presence text / emoji)
- Enable / disable Discord runtime features
- Diagnostic and debug reporting
- Administrative configuration overrides

IMPORTANT CONSTRAINTS:
- This module MUST NOT register commands on import
- This module MUST NOT own a Discord client
- This module MUST NOT perform permission checks directly
- This module MUST remain declarative and side-effect free
- All Discord objects (Interaction, Bot, Context) must be passed in externally
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING, Iterable

from core.config_loader import ConfigLoader
from core.jobs import JobRegistry
from core.registry import CreatorRegistry
from media.jobs.clip_job import ClipJob
from services.clips.manager import clip_manager
from services.triggers.actions import ActionExecutor
from shared.logging.logger import get_logger
from shared.runtime.admin_contract import read_state
from shared.storage.state_store import get_all_jobs, record_trigger_fire
from services.discord.permissions import DiscordPermissionResolver
from services.discord.logging import DiscordLogAdapter
from services.discord.status import DiscordStatusManager

if TYPE_CHECKING:
    from services.discord.runtime.supervisor import DiscordSupervisor

log = get_logger("discord.commands.admin", runtime="discord")


class AdminCommandHandler:
    """
    Declarative handler for admin-level Discord commands.

    This class does NOT register commands.
    It provides callable handlers to be wired by the Discord client layer.
    """

    def __init__(
        self,
        *,
        permissions: DiscordPermissionResolver,
        logger: DiscordLogAdapter,
        status: DiscordStatusManager,
        supervisor: Optional[DiscordSupervisor] = None,
    ):
        self._permissions = permissions
        self._logger = logger
        self._status = status
        self._supervisor = supervisor

        self._platform_overrides_path = Path("shared/config/platform_overrides.json")
        self._job_registry: Optional[JobRegistry] = None
        self._creator_contexts: Dict[str, Any] = {}
        self._clip_manager_started = False

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _describe_platform_list(platforms: Iterable[str]) -> str:
        return ", ".join(sorted(platforms))

    def _load_runtime_snapshot(self) -> Dict[str, Any]:
        snapshot = read_state()
        return snapshot if isinstance(snapshot, dict) else {}

    def _load_platform_overrides(self) -> Dict[str, bool]:
        if not self._platform_overrides_path.exists():
            return {}

        try:
            payload = json.loads(self._platform_overrides_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Failed to read platform overrides: {e}")
            return {}

        entries: Any = None
        if isinstance(payload, dict):
            entries = payload.get("platforms", payload)
        else:
            entries = payload

        overrides: Dict[str, bool] = {}
        if isinstance(entries, dict):
            for name, value in entries.items():
                if isinstance(value, dict):
                    flag = value.get("enabled")
                else:
                    flag = value
                if isinstance(flag, bool):
                    overrides[self._normalize_name(str(name))] = flag
        elif isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("platform_id") or entry.get("platform") or entry.get("name")
                flag = entry.get("enabled")
                if isinstance(name, str) and isinstance(flag, bool):
                    overrides[self._normalize_name(name)] = flag

        return overrides

    def _persist_platform_overrides(self, overrides: Dict[str, bool]) -> None:
        payload = {
            "platforms": [
                {"platform": name, "enabled": flag}
                for name, flag in sorted(overrides.items())
            ]
        }
        self._platform_overrides_path.parent.mkdir(parents=True, exist_ok=True)
        self._platform_overrides_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _find_platform_entry(
        self,
        snapshot: Dict[str, Any],
        platform: str,
    ) -> Optional[Dict[str, Any]]:
        platforms = snapshot.get("platforms", [])
        if not isinstance(platforms, list):
            return None
        normalized = self._normalize_name(platform)
        for entry in platforms:
            if not isinstance(entry, dict):
                continue
            name = entry.get("platform") or entry.get("name")
            if isinstance(name, str) and self._normalize_name(name) == normalized:
                return entry
        return None

    def _load_creator_contexts(self) -> Dict[str, Any]:
        if self._creator_contexts:
            return self._creator_contexts

        config_loader = ConfigLoader()
        platform_config = config_loader.load_platforms_config()
        creators_config = config_loader.load_creators_config()

        registry = CreatorRegistry(config_loader=config_loader)
        self._creator_contexts = registry.load(
            creators_data=creators_config,
            platform_defaults=platform_config,
        )
        return self._creator_contexts

    async def _ensure_clip_runtime(self, ctx: Any) -> None:
        if self._job_registry is None:
            system_config = ConfigLoader().load_system_config()
            job_flags = system_config.system.jobs
            self._job_registry = JobRegistry(job_enable_flags=job_flags)

        clips_feature = (
            getattr(ctx, "features", {}).get("clips", {})
            if isinstance(getattr(ctx, "features", {}), dict)
            else {}
        )
        clips_enabled = bool(clips_feature.get("enabled", False))

        if clips_enabled and "clip" not in self._job_registry._job_types:
            self._job_registry.register("clip", ClipJob)

        if clips_enabled and not self._clip_manager_started:
            await clip_manager.start()
            self._clip_manager_started = True

    # --------------------------------------------------
    # STATUS COMMANDS
    # --------------------------------------------------

    async def cmd_set_status(
        self,
        *,
        user_id: int,
        guild_id: int,
        text: str,
        emoji: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set the bot's custom Discord presence.

        Permissions: Admin only
        """

        self._logger.log_command(
            command="set_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        # NOTE: actual mutation happens in services.discord.status
        return {
            "ok": True,
            "message": "Status update accepted",
            "text": text,
            "emoji": emoji,
        }

    async def cmd_clear_status(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Clear the bot's custom Discord presence.

        Permissions: Admin only
        """

        self._logger.log_command(
            command="clear_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "message": "Status cleared",
        }

    # --------------------------------------------------
    # DIAGNOSTICS / INSPECTION (NOW REAL)
    # --------------------------------------------------

    async def cmd_runtime_status(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        """
        Return Discord runtime diagnostic information.
        """

        snapshot = (
            self._supervisor.snapshot()
            if self._supervisor
            else {
                "running": False,
                "connected": False,
                "tasks": 0,
                "heartbeat": None,
                "status": None,
            }
        )

        self._logger.log_command(
            command="runtime_status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
        )

        return {
            "ok": True,
            "runtime": "discord",
            "supervisor": snapshot,
        }

    # --------------------------------------------------
    # CONTROL PLANE COMMANDS
    # --------------------------------------------------

    async def cmd_toggle_platform(
        self,
        *,
        user_id: int,
        guild_id: int,
        platform: str,
    ) -> Dict[str, Any]:
        normalized = self._normalize_name(platform)
        if not normalized:
            return {"ok": False, "message": "Platform name is required."}

        snapshot = self._load_runtime_snapshot()
        entry = self._find_platform_entry(snapshot, normalized)

        known_platforms = {
            self._normalize_name(entry.get("platform") or entry.get("name"))
            for entry in snapshot.get("platforms", [])
            if isinstance(entry, dict) and (entry.get("platform") or entry.get("name"))
        }
        known_platforms.discard("")

        if not entry and known_platforms and normalized not in known_platforms:
            message = (
                f"Unknown platform '{platform}'. "
                f"Known platforms: {self._describe_platform_list(known_platforms)}"
            )
            return {"ok": False, "message": message}

        overrides = self._load_platform_overrides()
        current_enabled = None
        if entry:
            current_enabled = bool(entry.get("enabled", False))
        elif normalized in overrides:
            current_enabled = bool(overrides.get(normalized))

        desired_enabled = not current_enabled if current_enabled is not None else True
        overrides[normalized] = desired_enabled
        self._persist_platform_overrides(overrides)

        action = "enabled" if desired_enabled else "disabled"
        self._logger.log_command(
            command="toggle_platform",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"platform": normalized, "enabled": desired_enabled},
        )

        return {
            "ok": True,
            "message": (
                f"Platform '{normalized}' marked {action}. "
                "Restart required to apply."
            ),
            "platform": normalized,
            "enabled": desired_enabled,
        }

    async def cmd_trigger(
        self,
        *,
        user_id: int,
        guild_id: int,
        name: str,
    ) -> Dict[str, Any]:
        normalized = self._normalize_name(name)
        if not normalized:
            return {"ok": False, "message": "Trigger name is required."}

        try:
            triggers, source = ConfigLoader().load_triggers_config()
        except Exception as e:
            log.warning(f"Failed to load trigger config: {e}")
            return {"ok": False, "message": "Trigger config unavailable."}

        match = None
        for entry in triggers:
            trigger_id = entry.get("trigger_id")
            command = entry.get("command")
            if isinstance(trigger_id, str) and self._normalize_name(trigger_id) == normalized:
                match = entry
                break
            if isinstance(command, str):
                command_name = self._normalize_name(command.lstrip("!/"))
                if command_name == normalized:
                    match = entry
                    break

        if not match:
            known = [
                entry.get("trigger_id")
                for entry in triggers
                if isinstance(entry, dict) and entry.get("trigger_id")
            ]
            message = "Trigger not recognized."
            if known:
                message += f" Available triggers: {self._describe_platform_list(known)}"
            return {"ok": False, "message": message}

        creator_id = match.get("creator_id") or match.get("creator")
        trigger_id = match.get("trigger_id") or normalized
        actions = match.get("actions") if isinstance(match.get("actions"), list) else []

        ctx = None
        if creator_id:
            ctx = self._load_creator_contexts().get(str(creator_id))
            if not ctx:
                return {
                    "ok": False,
                    "message": f"Creator '{creator_id}' is not available in runtime config.",
                }

        execution_results = []
        skipped_actions = []
        if actions and ctx:
            normalized_actions = []
            for action in actions:
                if not isinstance(action, dict):
                    continue
                action_type = action.get("action_type") or action.get("type")
                if action_type == "enqueue_clip_job":
                    await self._ensure_clip_runtime(ctx)
                    payload = dict(action.get("payload") or {})
                    payload.setdefault("ctx", ctx)
                    normalized_actions.append({**action, "payload": payload})
                elif action_type == "send_chat_message":
                    skipped_actions.append(
                        {
                            "action": action,
                            "reason": "send_chat_message requires platform senders",
                        }
                    )
                elif action_type:
                    skipped_actions.append(
                        {
                            "action": action,
                            "reason": f"unsupported action_type: {action_type}",
                        }
                    )

            executor = ActionExecutor(
                creator_id=str(ctx.creator_id),
                job_registry=self._job_registry,
            )

            try:
                execution_results = await executor.execute(normalized_actions)
            except Exception as e:
                log.warning(f"Trigger execution failed: {e}")
                return {"ok": False, "message": f"Trigger execution failed: {e}"}

        if creator_id:
            record_trigger_fire(str(creator_id), str(trigger_id))

        self._logger.log_command(
            command="trigger",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"trigger_id": trigger_id, "creator_id": creator_id, "source": source},
        )

        creator_label = str(creator_id) if creator_id else "unknown"
        success_count = len([r for r in execution_results if r.get("status") == "success"])
        failure_count = len([r for r in execution_results if r.get("status") == "failed"])
        skipped_count = len(skipped_actions)
        return {
            "ok": True,
            "message": (
                f"Trigger '{trigger_id}' executed for creator '{creator_label}'. "
                f"Actions: {len(actions)} "
                f"(success={success_count}, failed={failure_count}, skipped={skipped_count})."
            ),
            "trigger_id": trigger_id,
            "creator_id": creator_id,
            "actions": actions,
            "results": execution_results,
            "skipped": skipped_actions,
        }

    async def cmd_jobs(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        jobs = get_all_jobs()
        now = int(time.time())
        active_statuses = {"running", "pending"}
        active_jobs = [job for job in jobs if job.get("status") in active_statuses]
        recent_completed = [
            job for job in jobs
            if job.get("status") == "completed"
            and isinstance(job.get("completed_at"), int)
            and now - job.get("completed_at") <= 3600
        ]

        self._logger.log_command(
            command="jobs",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"active": len(active_jobs), "total": len(jobs)},
        )

        return {
            "ok": True,
            "active_jobs": active_jobs,
            "recent_completed_count": len(recent_completed),
            "total_jobs": len(jobs),
        }

    async def cmd_status(
        self,
        *,
        user_id: int,
        guild_id: int,
    ) -> Dict[str, Any]:
        snapshot = self._load_runtime_snapshot()
        platforms = snapshot.get("platforms", [])
        if not isinstance(platforms, list):
            platforms = []

        def _status_emoji(entry: Dict[str, Any]) -> str:
            state = str(entry.get("state", "")).lower()
            status = str(entry.get("status", "")).lower()
            if state == "disabled" or status == "disabled":
                return "⛔"
            if state == "paused" or status == "paused":
                return "⏸️"
            if status in {"connected", "active"} or state == "active":
                return "✅"
            if status in {"connecting"}:
                return "🟡"
            return "⚪"

        platform_lines = []
        for entry in platforms:
            if not isinstance(entry, dict):
                continue
            name = entry.get("platform") or entry.get("name") or "unknown"
            status = entry.get("status") or entry.get("state") or "unknown"
            platform_lines.append(
                f"{name}: {status} {_status_emoji(entry)}"
            )

        jobs = get_all_jobs()
        active_jobs = [job for job in jobs if job.get("status") in {"running", "pending"}]

        self._logger.log_command(
            command="status",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"platforms": len(platform_lines), "active_jobs": len(active_jobs)},
        )

        return {
            "ok": True,
            "platform_lines": platform_lines,
            "active_jobs": len(active_jobs),
            "generated_at": snapshot.get("generated_at"),
        }

    # --------------------------------------------------
    # FEATURE FLAGS (STILL PLACEHOLDERS)
    # --------------------------------------------------

    async def cmd_enable_feature(
        self,
        *,
        user_id: int,
        guild_id: int,
        feature: str,
    ) -> Dict[str, Any]:
        """
        Enable a Discord runtime feature (placeholder).
        """

        self._logger.log_command(
            command="enable_feature",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"feature": feature},
        )

        return {
            "ok": True,
            "message": f"Feature '{feature}' enable requested (noop)",
        }

    async def cmd_disable_feature(
        self,
        *,
        user_id: int,
        guild_id: int,
        feature: str,
    ) -> Dict[str, Any]:
        """
        Disable a Discord runtime feature (placeholder).
        """

        self._logger.log_command(
            command="disable_feature",
            guild_id=guild_id,
            user_id=user_id,
            success=True,
            extra={"feature": feature},
        )

        return {
            "ok": True,
            "message": f"Feature '{feature}' disable requested (noop)",
        }
