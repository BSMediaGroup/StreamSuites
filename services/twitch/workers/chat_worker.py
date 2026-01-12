import asyncio
import time
from typing import Awaitable, Callable, Optional

from services.twitch.api.chat import TwitchChatClient
from services.twitch.models.message import TwitchChatMessage
from services.triggers.registry import TriggerRegistry
from services.triggers.validation import NonEmptyChatValidationTrigger
from services.triggers.actions import ActionExecutor
from shared.logging.logger import get_logger
from core.state_exporter import runtime_state, runtime_snapshot_exporter
from shared.chat.events import create_chat_event
from shared.storage.chat_events.writer import write_event
from shared.storage.state_store import get_last_trigger_time, record_trigger_fire

log = get_logger("twitch.chat_worker", runtime="streamsuites")


class TwitchChatWorker:
    """
    Scheduler-owned Twitch chat worker (IRC over TLS).

    Responsibilities:
    - Own the TwitchChatClient lifecycle (connect, read, send, shutdown)
    - Emit normalized chat events for future trigger routing
    - Remain cancellation-safe and free of side effects on import
    """

    COMMAND_PREFIX = "!"

    def __init__(
        self,
        *,
        ctx,
        oauth_token: str,
        channel: str,
        nickname: Optional[str] = None,
        action_executor: Optional[ActionExecutor] = None,
    ):
        if not oauth_token:
            raise RuntimeError("Twitch oauth_token is required")
        if not channel:
            raise RuntimeError("Twitch channel is required")

        self.ctx = ctx
        self.channel = channel
        self.nickname = nickname or channel

        self._client = TwitchChatClient(
            token=oauth_token,
            nickname=self.nickname,
            channel=self.channel,
        )

        self._stop_event = asyncio.Event()

        # --------------------------------------------------
        # Trigger registry (per-creator, per-platform)
        # --------------------------------------------------
        self._triggers = TriggerRegistry(creator_id=ctx.creator_id)
        self._triggers.register(NonEmptyChatValidationTrigger())
        self._actions = action_executor

        # --------------------------------------------------
        # Audience-facing command registry (Twitch only)
        # NOTE: Discord is for admin/control commands.
        # --------------------------------------------------
        self._command_handlers: dict[str, Callable[[TwitchChatMessage, list[str]], Awaitable[None]]] = {
            "ping": self._handle_ping_command,
            "clip": self._handle_clip_command,
        }

        self._clip_cooldown_seconds = self._resolve_clip_cooldown()
        self._default_clip_length = self._resolve_default_clip_length()

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker starting")
        backoff = 2.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                runtime_state.record_platform_status(
                    "twitch", "connecting", creator_id=self.ctx.creator_id
                )
                await self._client.connect()
                runtime_state.record_platform_status(
                    "twitch", "connected", creator_id=self.ctx.creator_id, success=True
                )

                async for message in self._client.iter_messages():
                    await self._handle_message(message)
                    if self._stop_event.is_set():
                        break

                if self._stop_event.is_set():
                    break

                # If we exit the loop without stop, treat as disconnect
                raise RuntimeError("Twitch connection closed; reconnecting")

            except asyncio.CancelledError:
                log.debug(f"[{self.ctx.creator_id}] Twitch chat worker cancelled")
                raise
            except Exception as e:
                runtime_state.record_platform_error("twitch", str(e), self.ctx.creator_id)
                log.warning(f"[{self.ctx.creator_id}] Twitch chat worker error: {e}")
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)
            else:
                backoff = 2.0

        await self.shutdown()

    async def shutdown(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        await self._client.close()
        runtime_state.record_platform_status("twitch", "inactive", creator_id=self.ctx.creator_id)
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker stopped")

    # ------------------------------------------------------------------ #

    async def send_message(self, text: str) -> None:
        """
        Public helper for future trigger dispatchers or operators.
        """
        await self._client.send_message(text)

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: TwitchChatMessage) -> None:
        """
        Internal routing hook for chat messages.
        """
        event = message.to_event()
        event["creator_id"] = self.ctx.creator_id
        event["platform"] = "twitch"

        runtime_state.record_platform_event("twitch", creator_id=self.ctx.creator_id)
        runtime_state.record_platform_heartbeat("twitch")

        log.info(
            f"[{self.ctx.creator_id}] [#{message.channel}] "
            f"{message.username}: {message.text}"
        )

        # --------------------------------------------------
        # Unified chat storage (authoritative)
        # --------------------------------------------------
        roles = [badge for badge in message.badges if badge in {"mod", "moderator", "admin"}]
        chat_event = create_chat_event(
            stream_id=f"twitch:{message.channel}",
            source_platform="twitch",
            author_id=message.user_id or message.username,
            display_name=message.username,
            text=message.text,
            badges=message.badges,
            roles=roles,
            ts=event.get("timestamp"),
            raw=event,
        )
        write_event(chat_event)

        # --------------------------------------------------
        # Trigger evaluation (no execution yet)
        # --------------------------------------------------
        actions = self._triggers.process(event)
        if actions:
            runtime_state.record_trigger_actions("twitch", len(actions), creator_id=self.ctx.creator_id)
        for action in actions:
            log.debug(
                f"[{self.ctx.creator_id}] Trigger action emitted: {action}"
            )

        if self._actions and actions:
            await self._actions.execute(actions, default_platform="twitch")

        if actions:
            try:
                runtime_snapshot_exporter.publish()
            except Exception:
                log.debug("Runtime snapshot publish skipped for Twitch trigger")

        # --------------------------------------------------
        # Audience-facing chat commands (public triggers only)
        # --------------------------------------------------
        await self._handle_command(message)

    def _resolve_clip_cooldown(self) -> float:
        limits = getattr(self.ctx, "limits", {}) or {}
        feature_cfg = (
            getattr(self.ctx, "features", {}).get("clips", {})
            if isinstance(getattr(self.ctx, "features", {}), dict)
            else {}
        )
        cooldown = limits.get(
            "clip_min_cooldown_seconds",
            feature_cfg.get("min_cooldown_seconds", 120),
        )
        try:
            return max(0.0, float(cooldown))
        except (TypeError, ValueError):
            return 120.0

    def _resolve_default_clip_length(self) -> int:
        limits = getattr(self.ctx, "limits", {}) or {}
        feature_cfg = (
            getattr(self.ctx, "features", {}).get("clips", {})
            if isinstance(getattr(self.ctx, "features", {}), dict)
            else {}
        )
        default_len = feature_cfg.get("default_length", 30)
        max_len = limits.get("clip_max_duration_seconds", feature_cfg.get("max_duration_seconds"))
        try:
            default_len = int(default_len)
        except (TypeError, ValueError):
            default_len = 30
        try:
            max_len = int(max_len) if max_len is not None else None
        except (TypeError, ValueError):
            max_len = None
        if max_len and default_len > max_len:
            return max_len
        return max(1, default_len)

    def _parse_command(self, text: str) -> tuple[str, list[str]] | None:
        content = text.strip()
        if not content.startswith(self.COMMAND_PREFIX):
            return None
        content = content[len(self.COMMAND_PREFIX):].strip()
        if not content:
            return None
        parts = content.split()
        return parts[0].lower(), parts[1:]

    def _is_self_message(self, message: TwitchChatMessage) -> bool:
        return message.username.lower() == self.nickname.lower()

    async def _handle_command(self, message: TwitchChatMessage) -> None:
        if self._is_self_message(message):
            return

        parsed = self._parse_command(message.text or "")
        if not parsed:
            return

        command, args = parsed
        handler = self._command_handlers.get(command)
        if not handler:
            return

        await handler(message, args)

    async def _handle_ping_command(self, message: TwitchChatMessage, args: list[str]) -> None:
        _ = args
        response = f"📢 StreamSuites Bot: @{message.username} Pong!"
        await self.send_message(response)

    async def _handle_clip_command(self, message: TwitchChatMessage, args: list[str]) -> None:
        _ = args
        clip_feature = (
            getattr(self.ctx, "features", {}).get("clips", {})
            if isinstance(getattr(self.ctx, "features", {}), dict)
            else {}
        )
        if not bool(clip_feature.get("enabled", False)):
            await self.send_message(
                "📢 StreamSuites Bot: Clips are not enabled for this channel."
            )
            return

        if not self._actions:
            await self.send_message(
                "📢 StreamSuites Bot: Clip requests are unavailable right now."
            )
            return

        active = self._actions.get_active_job_count("clip")
        if active is not None and active > 0:
            await self.send_message(
                "📢 StreamSuites Bot: A clip is already being processed. Please wait a moment."
            )
            return

        trigger_key = "twitch:clip"
        now = time.time()
        last = get_last_trigger_time(self.ctx.creator_id, trigger_key)
        if last is not None and (now - last) < self._clip_cooldown_seconds:
            remaining = int(self._clip_cooldown_seconds - (now - last))
            await self.send_message(
                f"📢 StreamSuites Bot: Clip command is on cooldown. Try again in {remaining}s."
            )
            return

        source_path = (getattr(self.ctx, "limits", {}) or {}).get("clip_source_path")
        if not source_path:
            await self.send_message(
                "📢 StreamSuites Bot: Clip source is not configured. Please ask the streamer."
            )
            return

        record_trigger_fire(self.ctx.creator_id, trigger_key, now)
        runtime_state.record_event(
            source="twitch",
            severity="info",
            message=f"Clip requested by {message.username} via chat command",
        )

        ack = (
            f"📢 StreamSuites Bot: @{message.username} clipping the last "
            f"{self._default_clip_length}s..."
        )
        await self.send_message(ack)

        payload = {
            "action_type": "enqueue_clip_job",
            "trigger_id": "twitch.command.clip",
            "platform": "twitch",
            "payload": {
                "ctx": self.ctx,
                "job_payload": {
                    "length": self._default_clip_length,
                    "source_path": source_path,
                    "start_seconds": 0.0,
                    "clipper_username": message.username,
                    "source_title": f"{self.ctx.display_name} Livestream",
                    "requested_by": f"twitch:{message.username}",
                },
            },
        }

        await self._actions.execute([payload], default_platform="twitch")
