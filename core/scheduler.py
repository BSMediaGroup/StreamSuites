import asyncio
import os
import time
from typing import Dict, List, Optional, Set

from core.context import CreatorContext
from core.state_exporter import runtime_state
from services.rumble.workers.livestream_worker import RumbleLivestreamWorker
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.twitch.workers.chat_worker import TwitchChatWorker
from services.youtube.workers.chat_worker import YouTubeChatWorker
from services.youtube.api.livestream import YouTubeLivestreamAPI
from services.discord.runtime.supervisor import DiscordSupervisor
from shared.logging.logger import get_logger
from shared.config.services import get_services_config

from shared.runtime.quotas import quota_snapshot_aggregator

log = get_logger("core.scheduler")


class Scheduler:
    # --------------------------------------------------
    # QUOTA SNAPSHOT CADENCE (PROCESS-WIDE, SINGLE WRITER)
    # --------------------------------------------------
    _last_quota_publish_ts: float = 0.0
    _quota_publish_interval: float = 60.0  # seconds

    def __init__(self, platforms_config: Optional[Dict[str, Dict[str, bool]]] = None):
        # creator_id -> list[asyncio.Task]
        self._tasks: Dict[str, List[asyncio.Task]] = {}

        # creator_id -> active job counts by type
        self._job_counts: Dict[str, Dict[str, int]] = {}

        # creator_id -> set[platform] actually started
        self._creator_platforms_started: Dict[str, Set[str]] = {}

        # Track which platforms were started (global, not per-creator)
        self._platforms_started: Set[str] = set()

        # Discord control-plane supervisor (process-scoped)
        self._discord_supervisor: Optional[DiscordSupervisor] = None

        # --------------------------------------------------
        # Load global service configuration ONCE
        # --------------------------------------------------
        self._services_cfg = self._normalize_platform_config(platforms_config or get_services_config())
        log.info(f"[BOOT] Loaded services configuration: {self._services_cfg}")

        for svc in ["youtube", "twitch", "rumble", "twitter", "discord"]:
            cfg = self._services_cfg.get(svc, {})
            enabled = cfg.get("enabled", True)
            telemetry_enabled = cfg.get("telemetry_enabled", enabled)
            log.info(
                f"[BOOT] Service '{svc}': "
                f"{'ENABLED' if enabled else 'DISABLED'} | "
                f"telemetry={'ON' if telemetry_enabled else 'OFF'}"
            )

        # --------------------------------------------------
        # Twitch runtime credentials (resolved once)
        # --------------------------------------------------
        self._twitch_oauth_token = os.getenv("TWITCH_OAUTH_TOKEN_DANIEL")
        self._twitch_channel = os.getenv("TWITCH_CHANNEL_DANIEL")
        self._twitch_nickname = os.getenv("TWITCH_BOT_NICK_DANIEL")

        log.debug(
            "[BOOT] Twitch credentials resolved: "
            f"token={'SET' if self._twitch_oauth_token else 'MISSING'}, "
            f"channel={'SET' if self._twitch_channel else 'MISSING'}, "
            f"nickname={'SET' if self._twitch_nickname else 'MISSING'}"
        )

        # --------------------------------------------------
        # YouTube runtime credentials (resolved once)
        # --------------------------------------------------
        self._youtube_api_key = os.getenv("YOUTUBE_API_KEY_DANIEL")
        log.debug(
            "[BOOT] YouTube API key resolved: "
            f"{'SET' if self._youtube_api_key else 'MISSING'}"
        )

    @staticmethod
    def _normalize_platform_config(cfg: Dict[str, Dict[str, bool]]) -> Dict[str, Dict[str, bool]]:
        normalized: Dict[str, Dict[str, bool]] = {}
        for name, entry in cfg.items():
            if isinstance(entry, dict):
                enabled = bool(entry.get("enabled", False))
                normalized[name] = {
                    "enabled": enabled,
                    "telemetry_enabled": bool(entry.get("telemetry_enabled", enabled)),
                }
            else:
                normalized[name] = {"enabled": False, "telemetry_enabled": False}
        return normalized

    # ------------------------------------------------------------

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"[{ctx.creator_id}] Starting creator runtime")

        if ctx.creator_id in self._tasks:
            log.warning(f"[{ctx.creator_id}] Runtime already started — skipping")
            return

        self._tasks[ctx.creator_id] = []
        self._job_counts[ctx.creator_id] = {}
        self._creator_platforms_started[ctx.creator_id] = set()

        # --------------------------------------------------
        # Heartbeat (always on)
        # --------------------------------------------------
        log.debug(f"[{ctx.creator_id}] Scheduling heartbeat task")
        heartbeat = asyncio.create_task(self._heartbeat(ctx))
        self._tasks[ctx.creator_id].append(heartbeat)

        # --------------------------------------------------
        # Rumble livestream + chat orchestration
        # --------------------------------------------------
        rumble_cfg = self._services_cfg.get("rumble", {})
        try:
            if not rumble_cfg.get("enabled", True):
                log.info(f"[{ctx.creator_id}] Rumble skipped (disabled by services.json)")
            elif not ctx.platform_enabled("rumble"):
                log.info(f"[{ctx.creator_id}] Rumble skipped (disabled for creator)")
            else:
                log.info(f"[{ctx.creator_id}] Rumble ENABLED — starting worker")
                self._platforms_started.add("rumble")
                self._creator_platforms_started[ctx.creator_id].add("rumble")
                runtime_state.record_platform_started("rumble", ctx.creator_id)

                livestream_worker = RumbleLivestreamWorker(
                    ctx=ctx,
                    jobs=self._get_job_registry()
                )
                task = asyncio.create_task(livestream_worker.run())
                self._tasks[ctx.creator_id].append(task)
        except Exception as e:
            runtime_state.record_platform_error("rumble", str(e), ctx.creator_id)
            raise

        # --------------------------------------------------
        # Twitch chat orchestration
        # --------------------------------------------------
        twitch_cfg = self._services_cfg.get("twitch", {})
        try:
            if not twitch_cfg.get("enabled", True):
                log.info(f"[{ctx.creator_id}] Twitch skipped (disabled by services.json)")
            elif not ctx.platform_enabled("twitch"):
                log.info(f"[{ctx.creator_id}] Twitch skipped (disabled for creator)")
            else:
                log.info(f"[{ctx.creator_id}] Twitch ENABLED — starting worker")

                if not self._twitch_oauth_token or not self._twitch_channel:
                    raise RuntimeError(
                        "Twitch enabled but required env vars are missing "
                        "(TWITCH_OAUTH_TOKEN_DANIEL, TWITCH_CHANNEL_DANIEL)"
                    )

                self._platforms_started.add("twitch")
                self._creator_platforms_started[ctx.creator_id].add("twitch")
                runtime_state.record_platform_started("twitch", ctx.creator_id)

                twitch_worker = TwitchChatWorker(
                    ctx=ctx,
                    oauth_token=self._twitch_oauth_token,
                    channel=self._twitch_channel,
                    nickname=self._twitch_nickname,
                )

                task = asyncio.create_task(twitch_worker.run())
                self._tasks[ctx.creator_id].append(task)
        except Exception as e:
            runtime_state.record_platform_error("twitch", str(e), ctx.creator_id)
            raise

        # --------------------------------------------------
        # YouTube chat orchestration
        # --------------------------------------------------
        youtube_cfg = self._services_cfg.get("youtube", {})
        try:
            if not youtube_cfg.get("enabled", True):
                log.info(f"[{ctx.creator_id}] YouTube skipped (disabled by services.json)")
            elif not ctx.platform_enabled("youtube"):
                log.info(f"[{ctx.creator_id}] YouTube skipped (disabled for creator)")
            else:
                log.info(f"[{ctx.creator_id}] YouTube ENABLED — checking livestream")

                if not self._youtube_api_key:
                    raise RuntimeError(
                        "YouTube enabled but YOUTUBE_API_KEY_DANIEL is missing"
                    )

                youtube_api = YouTubeLivestreamAPI(
                    api_key=self._youtube_api_key
                )

                livestream = await youtube_api.get_active_livestream(
                    channel_id=ctx.creator_id
                )

                if not livestream:
                    log.info(
                        f"[{ctx.creator_id}] No active YouTube livestream — worker not started"
                    )
                else:
                    log.info(
                        f"[{ctx.creator_id}] Active YouTube livestream detected — "
                        f"liveChatId={livestream.live_chat_id}"
                    )

                    self._platforms_started.add("youtube")
                    self._creator_platforms_started[ctx.creator_id].add("youtube")
                    runtime_state.record_platform_started("youtube", ctx.creator_id)

                    youtube_worker = YouTubeChatWorker(
                        ctx=ctx,
                        api_key=self._youtube_api_key,
                        live_chat_id=livestream.live_chat_id,
                    )

                    task = asyncio.create_task(youtube_worker.run())
                    self._tasks[ctx.creator_id].append(task)
        except Exception as e:
            runtime_state.record_platform_error("youtube", str(e), ctx.creator_id)
            raise

        # --------------------------------------------------
        # Discord control-plane runtime
        # --------------------------------------------------
        log.info(
            f"[{ctx.creator_id}] Discord control-plane is "
            "INTENTIONALLY DISABLED in main runtime"
        )

    # ------------------------------------------------------------

    async def _ensure_discord_runtime_started(self):
        """
        Discord is a separate runtime and must not start from core.app.
        This method is intentionally unreachable.
        """
        log.debug("Discord supervisor start blocked by design")
        return

    # ------------------------------------------------------------

    def can_start_job(self, ctx: CreatorContext, job_type: str) -> bool:
        limits = ctx.limits or {}

        if job_type == "clip":
            max_jobs = limits.get("max_concurrent_clip_jobs")
            if max_jobs is None:
                return True

            active = self._job_counts.get(ctx.creator_id, {}).get(job_type, 0)
            log.debug(
                f"[{ctx.creator_id}] Clip job check: "
                f"{active}/{max_jobs} active"
            )
            return active < max_jobs

        return True

    def register_job_start(self, ctx: CreatorContext, job_type: str):
        self._job_counts.setdefault(ctx.creator_id, {})
        self._job_counts[ctx.creator_id][job_type] = (
            self._job_counts[ctx.creator_id].get(job_type, 0) + 1
        )
        log.debug(
            f"[{ctx.creator_id}] Job started: {job_type} "
            f"(count={self._job_counts[ctx.creator_id][job_type]})"
        )

    def register_job_end(self, ctx: CreatorContext, job_type: str):
        try:
            self._job_counts[ctx.creator_id][job_type] -= 1
            log.debug(
                f"[{ctx.creator_id}] Job ended: {job_type} "
                f"(count={self._job_counts[ctx.creator_id].get(job_type, 0)})"
            )
            if self._job_counts[ctx.creator_id][job_type] <= 0:
                del self._job_counts[ctx.creator_id][job_type]
        except Exception:
            pass

    # ------------------------------------------------------------

    async def _heartbeat(self, ctx: CreatorContext):
        try:
            while True:
                log.debug(f"[{ctx.creator_id}] runtime heartbeat")

                runtime_state.record_creator_heartbeat(ctx.creator_id)
                for platform in self._creator_platforms_started.get(ctx.creator_id, set()):
                    runtime_state.record_platform_heartbeat(platform)

                # --------------------------------------------------
                # QUOTA SNAPSHOT CADENCE (GLOBAL THROTTLE)
                # Only one publish per interval, regardless of creators.
                # --------------------------------------------------
                now = time.time()
                if now - Scheduler._last_quota_publish_ts >= Scheduler._quota_publish_interval:
                    try:
                        quota_snapshot_aggregator.publish()
                        Scheduler._last_quota_publish_ts = now
                    except Exception as e:
                        log.warning(f"[quota] Snapshot publish failed: {e}")

                await asyncio.sleep(10)
        except asyncio.CancelledError:
            log.debug(f"[{ctx.creator_id}] heartbeat cancelled")
            raise

    # ------------------------------------------------------------

    async def shutdown(self):
        log.info("Scheduler shutdown initiated")

        log.info(f"Platforms started during session: {sorted(self._platforms_started)}")

        all_tasks: List[asyncio.Task] = [
            task for group in self._tasks.values() for task in group
        ]

        for task in all_tasks:
            if not task.done():
                task.cancel()

        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

        self._tasks.clear()
        self._job_counts.clear()
        self._creator_platforms_started.clear()

        if self._discord_supervisor:
            try:
                await self._discord_supervisor.shutdown()
            except Exception:
                pass
            self._discord_supervisor = None

        if "rumble" in self._platforms_started:
            try:
                log.info("Shutting down Rumble browser client")
                browser = RumbleBrowserClient.instance()
                await browser.shutdown()
            except Exception:
                pass

        self._platforms_started.clear()
        log.info("Scheduler shutdown complete")

    # ------------------------------------------------------------

    def _get_job_registry(self):
        from core.app import _GLOBAL_JOB_REGISTRY
        return _GLOBAL_JOB_REGISTRY
