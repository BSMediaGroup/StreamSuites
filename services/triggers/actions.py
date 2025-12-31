from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from shared.logging.logger import get_logger
from core.state_exporter import runtime_state

log = get_logger("triggers.actions", runtime="streamsuites")


class ActionExecutor:
    """
    Platform-agnostic action execution layer.

    Accepts action descriptors from the trigger registry and routes them to
    platform-specific senders or job dispatchers. Execution is best-effort and
    never raises to callers; errors are recorded in runtime telemetry instead.
    """

    def __init__(
        self,
        *,
        creator_id: str,
        job_registry: Optional[Any] = None,
    ) -> None:
        self.creator_id = creator_id
        self._senders: Dict[str, Callable[[str], Awaitable[None]]] = {}
        self._job_registry = job_registry

    # ------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------

    def register_platform_sender(
        self, platform: str, sender: Callable[[str], Awaitable[None]]
    ) -> None:
        if not platform or not sender:
            return
        self._senders[platform] = sender
        log.debug(
            f"[{self.creator_id}] Registered action sender for platform={platform}"
        )

    # ------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------

    async def execute(
        self, actions: List[Dict[str, Any]], *, default_platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for action in actions:
            descriptor = self._normalize_descriptor(action, default_platform)
            if not descriptor:
                continue

            try:
                log.info(
                    f"[{self.creator_id}] Executing action descriptor: {descriptor}"
                )
                await self._dispatch(descriptor)
                runtime_state.record_action_result(
                    descriptor["platform"],
                    success=True,
                    creator_id=self.creator_id,
                    action_type=descriptor.get("action_type"),
                    trigger_id=descriptor.get("trigger_id"),
                )
                results.append({"action": descriptor, "status": "success"})
            except Exception as e:
                err = str(e)
                log.warning(
                    f"[{self.creator_id}] Action execution failed "
                    f"(platform={descriptor.get('platform')}, "
                    f"type={descriptor.get('action_type')}): {err}"
                )
                runtime_state.record_action_result(
                    descriptor.get("platform", "unknown"),
                    success=False,
                    creator_id=self.creator_id,
                    action_type=descriptor.get("action_type"),
                    trigger_id=descriptor.get("trigger_id"),
                    error=err,
                )
                results.append(
                    {
                        "action": descriptor,
                        "status": "failed",
                        "error": err,
                    }
                )
        return results

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    def _normalize_descriptor(
        self, action: Dict[str, Any], default_platform: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(action, dict):
            return None

        action_type = action.get("action_type") or action.get("type")
        if not action_type:
            return None

        platform = action.get("platform") or default_platform
        payload = action.get("payload") or {}

        descriptor = {
            "action_type": action_type,
            "platform": platform,
            "payload": payload,
            "creator_id": action.get("creator_id") or self.creator_id,
            "trigger_id": action.get("trigger_id") or "unknown",
            "created_at": action.get("created_at")
            or datetime.now(timezone.utc).isoformat(),
        }
        return descriptor

    async def _dispatch(self, descriptor: Dict[str, Any]) -> None:
        action_type = descriptor["action_type"]
        platform = descriptor.get("platform")

        if action_type == "send_chat_message":
            await self._send_chat_message(platform, descriptor)
        elif action_type == "enqueue_clip_job":
            await self._enqueue_clip_job(descriptor)
        else:
            raise RuntimeError(f"Unsupported action_type: {action_type}")

    async def _send_chat_message(
        self, platform: Optional[str], descriptor: Dict[str, Any]
    ) -> None:
        if not platform:
            raise RuntimeError("send_chat_message requires a platform")

        sender = self._senders.get(platform)
        if not sender:
            raise RuntimeError(f"No sender registered for platform={platform}")

        payload = descriptor.get("payload") or {}
        text = (payload.get("text") or "").strip()
        if not text:
            raise RuntimeError("send_chat_message payload.text is required")

        await sender(text)

    async def _enqueue_clip_job(self, descriptor: Dict[str, Any]) -> None:
        if not self._job_registry:
            raise RuntimeError("Clip job requested but job registry is unavailable")

        payload = descriptor.get("payload") or {}
        ctx = payload.get("ctx")
        job_payload = payload.get("job_payload", {})

        if not ctx:
            raise RuntimeError("enqueue_clip_job payload.ctx is required")

        await self._job_registry.dispatch("clip", ctx, job_payload)
