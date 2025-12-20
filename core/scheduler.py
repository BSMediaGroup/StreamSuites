import asyncio
import os
from typing import Dict, List, Optional

from core.context import CreatorContext
from services.rumble.workers.livestream_worker import RumbleLivestreamWorker
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.twitch.workers.chat_worker import TwitchChatWorker
from services.youtube.workers.chat_worker import YouTubeChatWorker
from services.youtube.api.livestream import YouTubeLivestreamAPI
from services.discord.runtime.supervisor import DiscordSupervisor
from shared.logging.logger import get_logger
from shared.config.services import get_services_config

log = get_logger("core.scheduler")


class Scheduler:
    def __init__(self):
        # creator_id -> list[asyncio.Task]
        self._tasks: Dict[str, List[asyncio.Task]] = {}

        # creator_id -> active job counts by type
        self._job_counts: Dict[str, Dict[str, int]] = {}

        # Track which platforms were started (global, not per-creator)
        self._platforms_started: set[str] = set()

        # Discord control-plane supervisor (process-scoped)
        self._discord_supervisor: Optional[DiscordSupervisor] = None

        # --------------------------------------------------
        # Twitch runtime credentials (resolved once)
        # --------------------------------------------------
        self._twitch_oauth_token = os.getenv("TWITCH_OAUTH_TOKEN_DANIEL")
        self._twitch_channel = os.getenv("TWITCH_CHANNEL_DANIEL")
        self._twitch_nickname = os.getenv("TWITCH_BOT_NICK_DANIEL")

        # --------------------------------------------------
        # YouTube runtime credentials (resolved once)
        # --------------------------------------------------
        self._youtube_api_key = os.getenv("YOUTUBE_API_KEY_DANIEL")

    # ------------------------------------------------------------

    async def start_creator(self, ctx: CreatorContext):
        log.info(f"Starting creator runtime: {ctx.creator_id}")

        if ctx.creator_id in self._tasks:
            log.warning(f"[{ctx.creator_id}] runtime already started")
            return

        self._tasks[ctx.creator_id] = []
        self._job_counts[ctx.creator_id] = {}

        # --------------------------------------------------
        # Heartbeat (always on)
        # --------------------------------------------------
        heartbeat = asyncio.create_task(self._heartbeat(ctx))
        self._tasks[ctx.creator_id].append(heartbeat)

        # --------------------------------------------------
        # Rumble livestream + chat orchestration
        # --------------------------------------------------
        if ctx.platform_enabled("rumble"):
            self._platforms_started.add("rumble")

            livestream_worker = RumbleLivestreamWorker(
                ctx=ctx,
                jobs=self._get_job_registry()
            )
            task = asyncio.create_task(livestream_worker.run())
            self._tasks[ctx.creator_id].append(task)

        # --------------------------------------------------
        # Twitch chat orchestration (per-creator)
        # --------------------------------------------------
        if ctx.platform_enabled("twitch"):
            if not self._twitch_oauth_token or not self._twitch_channel:
                raise RuntimeError(
                    "Twitch platform enabled but required env vars are missing "
                    "(TWITCH_OAUTH_TOKEN_DANIEL, TWITCH_CHANNEL_DANIEL)"
                )

            self._platforms_started.add("twitch")

            twitch_worker = TwitchChatWorker(
                ctx=ctx,
                oauth_token=self._twitch_oauth_token,
                channel=self._twitch_channel,
                nickname=self._twitch_nickname,
            )

            task = asyncio.create_task(twitch_worker.run())
            self._tasks[ctx.creator_id].append(task)

        # --------------------------------------------------
        # YouTube chat orchestration (dynamic livestream)
        # --------------------------------------------------
        if ctx.platform_enabled("youtube"):
            if not self._youtube_api_key:
                raise RuntimeError(
                    "YouTube platform enabled but YOUTUBE_API_KEY_DANIEL is missing"
                )

            youtube_api = YouTubeLivestreamAPI(
                api_key=self._youtube_api_key
            )

            livestream = await youtube_api.get_active_livestream(
                channel_id=ctx.creator_id  # channel/@handle resolution handled upstream
            )

            if not livestream:
                log.info(
                    f"[{ctx.creator_id}] No active YouTube livestream detected; "
                    "chat worker not started"
                )
            else:
                self._platforms_started.add("youtube")

                youtube_worker = YouTubeChatWorker(
                    ctx=ctx,
                    api_key=self._youtube_api_key,
                    live_chat_id=livestream.live_chat_id,
                )

                task = asyncio.create_task(youtube_worker.run())
                self._tasks[ctx.creator_id].append(task)

        # --------------------------------------------------
        # Discord control-plane runtime (start once, feature-gated)
        # --------------------------------------------------
        await self._ensure_discord_runtime_started()

    # ------------------------------------------------------------

    async def _ensure_discord_runtime_started(self):
        if self._discord_supervisor:
            return

        services_cfg = get_services_config()
        discord_cfg = services_cfg.get("discord", {})

        if not discord_cfg.get("enabled", False):
            return

        log.info("Starting Discord control-plane runtime")

        self._discord_supervisor = DiscordSupervisor()
        await self._discord_supervisor.start()

    # ------------------------------------------------------------

    def can_start_job(self, ctx: CreatorContext, job_type: str) -> bool:
        limits = ctx.limits or {}

        if job_type == "clip":
            max_jobs = limits.get("max_concurrent_clip_jobs")
            if max_jobs is None:
                return True

            active = self._job_counts.get(ctx.creator_id, {}).get(job_type, 0)
            return active < max_jobs

        return True

    def register_job_start(self, ctx: CreatorContext, job_type: str):
        self._job_counts.setdefault(ctx.creator_id, {})
        self._job_counts[ctx.creator_id][job_type] = (
            self._job_counts[ctx.creator_id].get(job_type, 0) + 1
        )

    def register_job_end(self, ctx: CreatorContext, job_type: str):
        try:
            self._job_counts[ctx.creator_id][job_type] -= 1
            if self._job_counts[ctx.creator_id][job_type] <= 0:
                del self._job_counts[ctx.creator_id][job_type]
        except Exception:
            pass

    # ------------------------------------------------------------

    async def _heartbeat(self, ctx: CreatorContext):
        try:
            while True:
                log.debug(f"[{ctx.creator_id}] runtime heartbeat")
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            log.debug(f"[{ctx.creator_id}] heartbeat cancelled")
            raise

    # ------------------------------------------------------------

    async def shutdown(self):
        log.info("Scheduler shutdown initiated")

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

        if self._discord_supervisor:
            try:
                await self._discord_supervisor.shutdown()
            except Exception:
                pass
            self._discord_supervisor = None

        if "rumble" in self._platforms_started:
            try:
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
