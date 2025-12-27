import asyncio
import json
from pathlib import Path
from typing import Optional, Set, Tuple, Dict, Any, List, Union
from datetime import datetime, timezone

import httpx

from core.jobs import JobRegistry
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.rumble.chat.sse_client import RumbleChatSSEClient, SSEUnavailable
from shared.logging.logger import get_logger

# ------------------------------------------------------------
# B3: Persistent trigger cooldowns via state_store (preferred)
# Falls back to in-memory dict ONLY if state_store functions
# are not present (safety; does NOT affect normal operation).
# ------------------------------------------------------------
try:
    from shared.storage.state_store import get_last_trigger_time, record_trigger_fire  # type: ignore
except Exception:
    get_last_trigger_time = None  # type: ignore
    record_trigger_fire = None  # type: ignore

log = get_logger("rumble.chat_worker")

# Default fallbacks (used only if config missing/unreadable)
DEFAULT_POLL_SECONDS = 2
DEFAULT_SEND_COOLDOWN_SECONDS = 0.75
DEFAULT_STARTUP_ANNOUNCEMENT = "🤖 StreamSuites bot online"

CONFIG_PATH = Path("shared") / "config" / "chat_behaviour.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_created_on(created_raw: Union[str, int, float, None]) -> Optional[datetime]:
    """
    POC compatibility fix:
    Rumble 'created_on' may be:
      - ISO 8601 string (often with Z)
      - epoch seconds (int/float)
      - epoch milliseconds (int/float)

    If we fail to parse, the message is dropped (same behavior as before),
    but we now correctly parse the common non-ISO variants to prevent a
    total "no messages seen" failure.
    """
    if created_raw is None:
        return None

    # Numeric epoch handling (seconds or ms)
    if isinstance(created_raw, (int, float)):
        try:
            v = float(created_raw)
            # Heuristic: ms timestamps are typically > 1e12
            if v > 1_000_000_000_000:
                v = v / 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None

    # String ISO handling
    if isinstance(created_raw, str):
        if not created_raw:
            return None
        try:
            # Rumble often uses ISO with +00:00; sometimes "Z"
            return datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except Exception:
            return None

    return None


class RumbleChatWorker:
    """
    MODEL A — CHAT WORKER (POC-FAITHFUL, HARDENED)

    READ: SSE endpoint (authoritative, replaces livestream API polling)
    SEND: DOM injection (Playwright keyboard)

    HARD RULES:
    - On startup: establish a baseline cutoff BEFORE announcing or responding
    - Only respond to messages strictly AFTER the baseline cutoff
    - Rate-limit outgoing sends to avoid flooding / platform rate limits
    """

    def __init__(
        self,
        ctx,
        jobs: JobRegistry,
        watch_url: str,
    ):
        self.ctx = ctx
        self.jobs = jobs
        self.watch_url = watch_url

        self.browser: Optional[RumbleBrowserClient] = None

        # SSE client (authoritative chat ingest). We keep it None until
        # run() to ensure we only connect once the browser/session is ready.
        self._sse_client: Optional[RumbleChatSSEClient] = None

        # De-dup key: (username, text, created_on_raw_str)
        self._seen: Set[Tuple[str, str, str]] = set()

        # Concurrency + rate limiting
        self._send_lock = asyncio.Lock()
        self._last_send_ts: float = 0.0

        # Baseline cutoff (set during startup sync)
        self._baseline_cutoff: Optional[datetime] = None
        self._baseline_ready: bool = False

        # Ingest mode tracking ("sse" | "api_poll")
        self._ingest_mode: str = "sse"

        # Config
        self._cfg: Dict[str, Any] = {}
        self._poll_seconds: float = float(DEFAULT_POLL_SECONDS)
        self._send_cooldown_seconds: float = float(DEFAULT_SEND_COOLDOWN_SECONDS)
        self._startup_announcement: str = DEFAULT_STARTUP_ANNOUNCEMENT
        self._enable_startup_announcement: bool = True

        self._triggers: List[Dict[str, Any]] = []

        # ------------------------------------------------------------
        # B3: Trigger cooldown tracking (in-memory, per worker)
        # Keyed by trigger identity (match + mode)
        #
        # NOTE:
        # Preferred persistence is via shared.storage.state_store:
        #   get_last_trigger_time / record_trigger_fire
        # This dict remains ONLY as a safe fallback if those functions
        # are not available at runtime.
        # ------------------------------------------------------------
        self._trigger_last_fired: Dict[str, float] = {}

        self._poll_count = 0

        # Keep track of the last SSE message id we processed to avoid dupes
        # across reconnects. The SSE client also manages Last-Event-ID, but
        # we guard downstream handling to remain idempotent.
        self._last_sse_id: Optional[str] = None

        # Cookie jar reused by SSE client to mirror browser auth
        self._sse_cookies: httpx.Cookies = httpx.Cookies()
        self._sse_cookie_header: str = ""
        self._sse_headers: Dict[str, str] = {}

    # ------------------------------------------------------------

    def _load_config(self) -> None:
        cfg: Dict[str, Any] = {}
        try:
            if CONFIG_PATH.exists():
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                log.info(f"[{self.ctx.creator_id}] Loaded chat config → {CONFIG_PATH.as_posix()}")
            else:
                log.warning(f"[{self.ctx.creator_id}] Chat config missing → {CONFIG_PATH.as_posix()} (using defaults)")
        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Failed to load chat config: {e} (using defaults)")
            cfg = {}

        self._cfg = cfg

        self._poll_seconds = float(cfg.get("poll_seconds", DEFAULT_POLL_SECONDS))
        self._send_cooldown_seconds = float(cfg.get("send_cooldown_seconds", DEFAULT_SEND_COOLDOWN_SECONDS))
        self._startup_announcement = str(cfg.get("startup_announcement", DEFAULT_STARTUP_ANNOUNCEMENT))
        self._enable_startup_announcement = bool(cfg.get("enable_startup_announcement", True))

        self._triggers = cfg.get("triggers", [])
        if not isinstance(self._triggers, list):
            self._triggers = []

    # ------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        self.browser = RumbleBrowserClient.instance()

        if not self.browser.started:
            raise RuntimeError(
                "Browser must be started by RumbleLivestreamWorker before chat worker begins"
            )

        log.info(f"[{self.ctx.creator_id}] Navigating to livestream → {self.watch_url}")

        await self.browser.open_watch(self.watch_url)
        await self.browser.wait_for_chat_ready()

    # ------------------------------------------------------------

    async def _hydrate_sse_cookies(self) -> None:
        if not self.browser:
            return

        try:
            cookies = await self.browser.export_cookies(
                for_domains=["rumble.com", ".rumble.com", "web7.rumble.com"]
            )
        except Exception as e:
            log.warning(f"[{self.ctx.creator_id}] Unable to export cookies for SSE: {e}")
            return

        jar = httpx.Cookies()
        cookie_header_parts: List[str] = []

        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if not name or value is None:
                continue

            domain = c.get("domain") or "rumble.com"
            path = c.get("path") or "/"

            try:
                jar.set(name, value, domain=domain, path=path)
            except Exception:
                continue

            cookie_header_parts.append(f"{name}={value}")

        if not jar:
            log.warning(f"[{self.ctx.creator_id}] No cookies captured for SSE auth")
        else:
            log.info(f"[{self.ctx.creator_id}] Loaded {len(jar)} cookies for SSE auth")
            log.debug(f"[{self.ctx.creator_id}] SSE cookie header parts: {cookie_header_parts}")

        self._sse_cookies = jar
        self._sse_cookie_header = "; ".join(cookie_header_parts)

    # ------------------------------------------------------------

    async def _hydrate_sse_headers(self) -> None:
        if not self.browser or not self.browser._page:
            log.warning(f"[{self.ctx.creator_id}] Browser not ready for SSE header capture")
            return

        user_agent: Optional[str] = None
        try:
            user_agent = await self.browser._page.evaluate("navigator.userAgent")
        except Exception:
            try:
                # Fallback to Playwright context property if evaluate fails
                user_agent = getattr(self.browser._context, "user_agent", None)
            except Exception:
                user_agent = None

        if not user_agent:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        self._sse_headers = {
            "User-Agent": user_agent,
            "Origin": "https://rumble.com",
            "Referer": self.watch_url,
        }

        log.debug(f"[{self.ctx.creator_id}] SSE headers prepared: {self._sse_headers}")

    # ------------------------------------------------------------

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Chat worker starting (API READ / DOM SEND)")

        if not self.ctx.rumble_livestream_api_url:
            raise RuntimeError(f"[{self.ctx.creator_id}] rumble_livestream_api_url is missing")

        log.info(f"[{self.ctx.creator_id}] Livestream API URL resolved → {self.ctx.rumble_livestream_api_url}")

        # Load external behavior config
        self._load_config()

        # Ensure browser + chat iframe locked (retained for DOM send path)
        await self._ensure_browser()

        # Export authenticated cookies for SSE ingest
        await self._hydrate_sse_cookies()

        # Prepare browser-aligned headers for SSE (must mirror the Playwright session)
        await self._hydrate_sse_headers()

        # Initialize SSE ingest client. We defer creation until here to avoid
        # building HTTP clients before the runtime is fully started.
        chat_id = self.ctx.rumble_chat_channel_id
        if not chat_id:
            raise RuntimeError(f"[{self.ctx.creator_id}] rumble_chat_channel_id is required for SSE ingest")

        self._sse_client = RumbleChatSSEClient(
            chat_id,
            cookies=self._sse_cookies,
            cookie_header=self._sse_cookie_header,
            watch_url=self.watch_url,
            headers=self._sse_headers,
        )

        # 1) Establish baseline cutoff FIRST (prevents historic spam on boot)
        await self._establish_startup_baseline()

        # 2) Announce only AFTER baseline exists
        if self._enable_startup_announcement and self._startup_announcement.strip():
            await self._send_text(self._startup_announcement.strip(), reason="startup_announcement")

        log.info(f"[{self.ctx.creator_id}] Chat ready — selecting ingest mode")

        try:
            await self._run_ingest_with_fallback()
        finally:
            await self._shutdown_sse()

    # ------------------------------------------------------------

    async def _api_get_data(self) -> Dict[str, Any]:
        if not self.browser or not self.browser._context:
            raise RuntimeError("Browser context not ready")

        response = await self.browser._context.request.get(
            self.ctx.rumble_livestream_api_url,
            timeout=10000,
            headers={"Accept": "application/json"},
        )

        status = response.status
        if status != 200:
            body = await response.text()
            body_preview = body[:500].replace("\n", "\\n")
            raise RuntimeError(f"Livestream API HTTP {status} body={body_preview}")

        try:
            return await response.json()
        except Exception:
            body = await response.text()
            body_preview = body[:500].replace("\n", "\\n")
            raise RuntimeError(f"Livestream API returned non-JSON: {body_preview}")

    # ------------------------------------------------------------

    async def _establish_startup_baseline(self) -> None:
        """
        Sets baseline cutoff to the newest created_on found in current recent_messages.
        This prevents reacting to the backscroll / history on boot.

        Important: this runs AFTER chat iframe is ready, but BEFORE any announcement.
        """
        log.info(f"[{self.ctx.creator_id}] Establishing startup baseline (history cutoff)")

        data = await self._api_get_data()

        streams = data.get("livestreams", []) or []
        if not isinstance(streams, list):
            log.warning(f"[{self.ctx.creator_id}] Baseline: invalid livestreams structure; falling back to now()")
            self._baseline_cutoff = _utc_now()
            self._baseline_ready = True
            return

        live_streams = [s for s in streams if s.get("is_live")]
        newest: Optional[datetime] = None

        for stream in live_streams:
            chat = stream.get("chat", {}) or {}
            recent = chat.get("recent_messages", []) or []
            if not isinstance(recent, list):
                continue

            for msg in recent:
                created_raw = msg.get("created_on")
                created_ts = _parse_created_on(created_raw)
                if not created_ts:
                    continue
                if (newest is None) or (created_ts > newest):
                    newest = created_ts

                # Also mark these as seen so we don't reprocess them immediately
                created_raw_str = str(created_raw)
                key = (msg.get("username"), msg.get("text"), created_raw_str)
                self._seen.add(key)

        # If no messages exist, still set a cutoff
        self._baseline_cutoff = newest if newest else _utc_now()
        self._baseline_ready = True

        log.info(f"[{self.ctx.creator_id}] Baseline cutoff set → {self._baseline_cutoff.isoformat()}")

    # ------------------------------------------------------------

    async def _run_ingest_with_fallback(self) -> None:
        """
        Primary ingest orchestrator. SSE is preferred but explicitly optional.
        If SSE is rejected (e.g., HTTP 204) we downgrade to livestream API
        polling while preserving the same baseline cutoff behavior.
        """

        self._ingest_mode = "sse"
        log.info(
            f"[{self.ctx.creator_id}] Ingest mode selected → {self._ingest_mode}"
        )

        while True:
            if self._ingest_mode == "sse":
                try:
                    await self._run_sse_loop()
                except SSEUnavailable as e:
                    log.warning(
                        f"[{self.ctx.creator_id}] SSE unavailable ({e}); switching to livestream API polling fallback"
                    )
                    await self._shutdown_sse()
                    self._ingest_mode = "api_poll"
                    log.info(
                        f"[{self.ctx.creator_id}] Ingest mode selected → {self._ingest_mode}"
                    )
                    continue

                # _run_sse_loop only returns on cancellation or shutdown
                return

            if self._ingest_mode == "api_poll":
                await self._run_api_poll_loop()
                return

            # Defensive: if mode is ever unset, default to polling to avoid spin
            log.warning(
                f"[{self.ctx.creator_id}] Unknown ingest mode {self._ingest_mode}; defaulting to API polling"
            )
            self._ingest_mode = "api_poll"

    # ------------------------------------------------------------

    async def _poll_recent_messages(self) -> None:
        """
        Fetch recent_messages from the livestream API and process any that are
        newer than the baseline. This path mirrors the baseline establishment
        logic but runs continuously when SSE is unavailable.
        """

        data = await self._api_get_data()
        streams = data.get("livestreams", []) or []
        if not isinstance(streams, list):
            log.warning(f"[{self.ctx.creator_id}] Poll: invalid livestreams structure")
            return

        live_streams = [s for s in streams if s.get("is_live")]
        for stream in live_streams:
            chat = stream.get("chat", {}) or {}
            recent = chat.get("recent_messages", []) or []
            if not isinstance(recent, list):
                continue

            for msg in recent:
                if not isinstance(msg, dict):
                    continue
                await self._handle_message_record(msg)

    # ------------------------------------------------------------

    async def _run_api_poll_loop(self) -> None:
        log.info(
            f"[{self.ctx.creator_id}] Entering livestream API polling ingest (interval={self._poll_seconds}s)"
        )

        while True:
            try:
                await self._poll_recent_messages()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning(f"[{self.ctx.creator_id}] Polling ingest error: {e}")

            await asyncio.sleep(self._poll_seconds)

    # ------------------------------------------------------------

    async def _run_sse_loop(self) -> None:
        if not self._sse_client:
            raise RuntimeError("SSE client not initialized")

        if not self._baseline_ready or not self._baseline_cutoff:
            log.warning(f"[{self.ctx.creator_id}] Baseline not ready; SSE loop waiting")
            await asyncio.sleep(1)

        try:
            async for event in self._sse_client.iter_events():
                try:
                    await self._handle_sse_event(event)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error(f"[{self.ctx.creator_id}] SSE event handling error: {e}")
        except SSEUnavailable:
            raise
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning(f"[{self.ctx.creator_id}] SSE loop aborted: {e}")

    # ------------------------------------------------------------

    async def _handle_sse_event(self, event) -> None:
        # Basic idempotency guard: if the SSE server replays an event id we
        # already processed (e.g., after reconnect), skip it. We store the
        # last seen id and expect monotonic progression from the backend.
        if event.event_id and event.event_id == self._last_sse_id:
            return

        self._last_sse_id = event.event_id or self._last_sse_id

        # The SSE payload is JSON per the confirmed Rumble endpoint contract.
        try:
            payload = json.loads(event.data)
        except Exception:
            log.warning(f"[{self.ctx.creator_id}] SSE payload not JSON; ignored")
            return

        if not isinstance(payload, dict):
            return

        event_type = payload.get("type") or event.event

        # The stream emits "init" then "messages" batches. We process both
        # through the same handler because "init" carries the initial data
        # sets (messages/users/channels/config/pinned_message).
        if event_type not in {"init", "messages"}:
            return

        payload_data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        messages = payload_data.get("messages") or []
        if not isinstance(messages, list):
            return

        for msg in messages:
            if not isinstance(msg, dict):
                continue

            await self._handle_message_record(msg)

    # ------------------------------------------------------------

    async def _handle_message_record(self, msg: Dict[str, Any]) -> None:
        created_raw = msg.get("created_on") or msg.get("created_at")
        if created_raw is None:
            return

        created_raw_str = str(created_raw)

        key = (msg.get("user_id") or msg.get("username"), msg.get("text"), created_raw_str)
        if key in self._seen:
            return
        self._seen.add(key)

        created_ts = _parse_created_on(created_raw)
        if not created_ts:
            return

        # HARD RULE: ignore anything at/before baseline cutoff
        if self._baseline_cutoff and created_ts <= self._baseline_cutoff:
            return

        user = (msg.get("user_name") or msg.get("username") or "").strip()
        text = (msg.get("text") or "").strip()
        if not user or not text:
            return

        log.info(f"💬 {user}: {text} (created_on={created_raw_str})")

        # Trigger evaluation
        await self._handle_triggers(user=user, text=text)

    # ------------------------------------------------------------

    async def _shutdown_sse(self) -> None:
        if self._sse_client:
            try:
                await self._sse_client.aclose()
            except Exception:
                pass
            self._sse_client = None

    # ------------------------------------------------------------

    async def _handle_triggers(self, user: str, text: str) -> None:
        """
        Very small trigger engine.
        For now it supports:
          - equals_icase
          - contains_icase
        """
        if not self._triggers:
            # Backwards-compatible default behavior
            if text.lower() == "!ping":
                await self._send_text("pong", reason=f"trigger_default(!ping) user={user}")
            return

        t = text.strip()
        tl = t.lower()

        now = asyncio.get_event_loop().time()

        for trig in self._triggers:
            if not isinstance(trig, dict):
                continue

            match = str(trig.get("match", "")).strip()
            if not match:
                continue

            mode = str(trig.get("match_mode", "equals_icase")).strip()
            response = str(trig.get("response", "")).strip()
            if not response:
                continue

            cooldown = trig.get("cooldown_seconds", None)
            try:
                cooldown_s = float(cooldown) if cooldown is not None else self._send_cooldown_seconds
            except Exception:
                cooldown_s = self._send_cooldown_seconds

            hit = False
            if mode == "equals_icase":
                hit = (tl == match.lower())
            elif mode == "contains_icase":
                hit = (match.lower() in tl)
            else:
                # Unknown mode — ignore
                continue

            if hit:
                trigger_key = f"{mode}:{match.lower()}"

                # ------------------------------------------------------------
                # B3: COOLDOWN CHECK (PERSISTENT via state_store preferred)
                # ------------------------------------------------------------
                last: Optional[float] = None

                if callable(get_last_trigger_time):
                    try:
                        last = get_last_trigger_time(self.ctx.creator_id, trigger_key)
                    except Exception as e:
                        log.warning(f"[{self.ctx.creator_id}] Trigger cooldown read failed (state_store): {e}")
                        last = None

                # Fallback to in-memory if state_store not available / failed
                if last is None:
                    last = self._trigger_last_fired.get(trigger_key)

                if last is not None:
                    delta = now - last
                    if delta < cooldown_s:
                        remaining = round(cooldown_s - delta, 2)
                        log.info(
                            f"[{self.ctx.creator_id}] Trigger '{match}' ignored "
                            f"(cooldown {remaining}s remaining)"
                        )
                        return

                # Record fire time (persistent preferred)
                if callable(record_trigger_fire):
                    try:
                        record_trigger_fire(self.ctx.creator_id, trigger_key, now)
                    except TypeError:
                        # If implementation doesn't accept 'now', call without it
                        try:
                            record_trigger_fire(self.ctx.creator_id, trigger_key)
                        except Exception as e:
                            log.warning(f"[{self.ctx.creator_id}] Trigger cooldown write failed (state_store): {e}")
                            self._trigger_last_fired[trigger_key] = now
                    except Exception as e:
                        log.warning(f"[{self.ctx.creator_id}] Trigger cooldown write failed (state_store): {e}")
                        self._trigger_last_fired[trigger_key] = now
                else:
                    self._trigger_last_fired[trigger_key] = now

                await self._send_text(
                    response,
                    reason=f"trigger({match}/{mode}) user={user}",
                    cooldown_override=cooldown_s
                )
                return

    # ------------------------------------------------------------

    async def _send_text(self, message: str, reason: str = "send", cooldown_override: Optional[float] = None) -> None:
        if not self.browser:
            log.error(f"[{self.ctx.creator_id}] Send failed (no browser) reason={reason}")
            return

        async with self._send_lock:
            # rate limit
            now = asyncio.get_event_loop().time()
            cooldown = cooldown_override if cooldown_override is not None else self._send_cooldown_seconds

            delta = now - self._last_send_ts
            if delta < cooldown:
                await asyncio.sleep(cooldown - delta)

            log.info(f"[{self.ctx.creator_id}] Sending chat message reason={reason} msg={message!r}")

            sent = await self.browser.send_chat_dom(message)

            if sent:
                self._last_send_ts = asyncio.get_event_loop().time()
                log.info(f"[{self.ctx.creator_id}] 📤 sent OK")
            else:
                log.error(f"[{self.ctx.creator_id}] ❌ send failed")
