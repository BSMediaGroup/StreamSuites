import asyncio
import json
from pathlib import Path
from typing import Optional, Set, Tuple, Dict, Any, List, Union
from types import SimpleNamespace
from datetime import datetime, timezone

from core.jobs import JobRegistry
from core.state_exporter import runtime_state
from services.rumble.browser.browser_client import RumbleBrowserClient
from services.rumble.chat.tombi_stream import StreamDisconnected, TombiStreamClient
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
    Authoritative Rumble chat worker

    READ: persistent HTTP stream from https://web7.rumble.com/chat/api/chat/{chat_id}/stream
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

        # De-dup key: (username, text, created_on_raw_str)
        self._seen: Set[Tuple[str, str, str]] = set()

        # Concurrency + rate limiting
        self._send_lock = asyncio.Lock()
        self._last_send_ts: float = 0.0

        # Baseline cutoff (set during startup sync)
        self._baseline_cutoff: Optional[datetime] = None
        self._baseline_ready: bool = False

        # Config
        self._cfg: Dict[str, Any] = {}
        self._send_cooldown_seconds: float = float(DEFAULT_SEND_COOLDOWN_SECONDS)
        self._startup_announcement: str = DEFAULT_STARTUP_ANNOUNCEMENT
        self._enable_startup_announcement: bool = True

        self._triggers: List[Dict[str, Any]] = []

        # Trigger cooldown tracking
        self._trigger_last_fired: Dict[str, float] = {}

        # Stream headers
        self._stream_headers: Dict[str, str] = {}
        self._stream_cookies: List[Dict[str, Any]] = []
        self._cookie_header: Optional[str] = None
        self._chat_id: Optional[str] = None

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

        current_url = getattr(self.browser._page, "url", "") if self.browser else ""
        if current_url != self.watch_url:
            log.info(f"[{self.ctx.creator_id}] Navigating to livestream → {self.watch_url}")
            await self.browser.open_watch(self.watch_url)
        else:
            log.info(f"[{self.ctx.creator_id}] Livestream already open — reusing existing page")

        await self.browser.wait_for_chat_ready()

    # ------------------------------------------------------------

    # ------------------------------------------------------------

    async def _hydrate_stream_headers(self) -> None:
        if not self.browser or not self.browser._page:
            log.warning(f"[{self.ctx.creator_id}] Browser not ready for chat header capture")
            return

        user_agent: Optional[str] = None
        try:
            user_agent = await self.browser._page.evaluate("navigator.userAgent")
        except Exception:
            try:
                user_agent = getattr(self.browser._context, "user_agent", None)
            except Exception:
                user_agent = None

        if not user_agent:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        self._stream_headers = {
            "User-Agent": user_agent,
            "Origin": "https://rumble.com",
            "Referer": self.watch_url,
        }

        log.debug(f"[{self.ctx.creator_id}] Chat stream headers prepared: {self._stream_headers}")

    # ------------------------------------------------------------

    async def _prepare_stream_cookies(self) -> None:
        if not self.browser:
            raise RuntimeError("Browser not ready for chat cookie capture")

        allowed_domains = [
            "rumble.com",
            "web7.rumble.com",
            "web6.rumble.com",
            "web5.rumble.com",
            "web4.rumble.com",
            "web3.rumble.com",
            "web2.rumble.com",
            "web1.rumble.com",
        ]

        cookies = await self.browser.export_cookies(for_domains=allowed_domains)
        header_parts = []
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if name and value:
                header_parts.append(f"{name}={value}")

        cookie_header = "; ".join(header_parts)

        if not cookie_header:
            raise RuntimeError(
                f"[{self.ctx.creator_id}] No cookies exported for chat stream authentication"
            )

        self._stream_cookies = cookies
        self._cookie_header = cookie_header

        log.info(
            f"[{self.ctx.creator_id}] Captured {len(cookies)} cookies for chat stream auth"
        )

    # ------------------------------------------------------------

    async def _resolve_chat_id(self) -> str:
        if not self.browser or not self.browser._page:
            raise RuntimeError("Browser not ready for chat_id resolution")

        chat_id = await self.browser.wait_for_chat_stream_id(self.watch_url, timeout=15.0)

        if not chat_id or not chat_id.isdigit():
            raise RuntimeError(
                f"[{self.ctx.creator_id}] Unable to resolve numeric chat_id from network request"
            )

        self._persist_chat_id(chat_id)

        runtime_ns = getattr(self.ctx, "runtime", None)
        if runtime_ns is None:
            runtime_ns = SimpleNamespace()
            self.ctx.runtime = runtime_ns  # type: ignore[attr-defined]

        rumble_ns = getattr(runtime_ns, "rumble", None)
        if rumble_ns is None:
            rumble_ns = SimpleNamespace()
            setattr(runtime_ns, "rumble", rumble_ns)

        rumble_ns.chat_id = chat_id
        self.ctx.rumble_chat_channel_id = chat_id
        self._chat_id = chat_id

        log.info(f"[{self.ctx.creator_id}] Resolved Rumble chat_id={chat_id} from network request")
        return chat_id

    # ------------------------------------------------------------

    def _persist_chat_id(self, chat_id: str) -> None:
        creators_path = Path("shared") / "config" / "creators.json"
        try:
            data = json.loads(creators_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] Failed to read creators.json for chat_id persist: {e}"
            )
            return

        creators = data.get("creators")
        if not isinstance(creators, list):
            log.error(
                f"[{self.ctx.creator_id}] creators.json missing 'creators' array — cannot persist chat_id"
            )
            return

        updated = False
        for entry in creators:
            if isinstance(entry, dict) and entry.get("creator_id") == self.ctx.creator_id:
                entry["rumble_chat_channel_id"] = chat_id
                updated = True
                break

        if not updated:
            log.error(
                f"[{self.ctx.creator_id}] Creator not found in creators.json — cannot persist chat_id"
            )
            return

        try:
            creators_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            log.info(
                f"[{self.ctx.creator_id}] Persisted chat_id={chat_id} to {creators_path.as_posix()}"
            )
        except Exception as e:
            log.error(
                f"[{self.ctx.creator_id}] Failed to write creators.json for chat_id persist: {e}"
            )

    # ------------------------------------------------------------

    async def run(self):
        log.info(f"[{self.ctx.creator_id}] Chat worker starting (authoritative HTTP ingest / DOM SEND)")

        # Load external behavior config
        self._load_config()

        chat_id: Optional[str] = None

        try:
            # Ensure browser + chat iframe locked (retained for DOM send path)
            await self._ensure_browser()

            # Prepare browser-aligned headers for stream (must mirror the Playwright session)
            await self._hydrate_stream_headers()
            await self._prepare_stream_cookies()

            chat_id = await self._resolve_chat_id()
            runtime_state.record_rumble_chat_status(
                chat_id=chat_id,
                status="CONNECTING",
                error=None,
            )

            # Establish baseline cutoff BEFORE announcing or responding
            self._baseline_cutoff = _utc_now()
            self._baseline_ready = True
            log.info(f"[{self.ctx.creator_id}] Baseline (startup now) → {self._baseline_cutoff.isoformat()}")

            # Announce only AFTER baseline exists
            if self._enable_startup_announcement and self._startup_announcement.strip():
                await self._send_text(self._startup_announcement.strip(), reason="startup_announcement")

            log.info(f"[{self.ctx.creator_id}] Chat ready — starting authoritative chat ingest")

            await self._run_stream_loop(chat_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            runtime_state.record_rumble_chat_status(
                chat_id=chat_id or self._chat_id or getattr(self.ctx, "rumble_chat_channel_id", None),
                status="FAILED",
                error=str(e),
            )
            raise

    # ------------------------------------------------------------

    async def _run_stream_loop(self, chat_id: str) -> None:
        backoff = 1.0
        while True:
            try:
                await self._consume_stream(chat_id)
                log.warning(f"[{self.ctx.creator_id}] Chat stream disconnected — scheduling reconnect")
            except asyncio.CancelledError:
                raise
            except StreamDisconnected as e:
                log.warning(f"[{self.ctx.creator_id}] Chat stream disconnected: {e}")
            except Exception as e:
                log.error(f"[{self.ctx.creator_id}] Chat stream error: {e}")

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _consume_stream(self, chat_id: str) -> None:
        headers = dict(self._stream_headers)
        headers.setdefault("Referer", self.watch_url)
        headers.setdefault("User-Agent", self._stream_headers.get("User-Agent", ""))

        client = TombiStreamClient(
            chat_id,
            headers=headers,
            cookies=self._stream_cookies,
            cookie_header=self._cookie_header,
            watch_url=self.watch_url,
        )
        total_messages = 0
        first_logged = False

        try:
            stream = client.iter_messages()

            try:
                first_message = await asyncio.wait_for(stream.__anext__(), timeout=10.0)
            except asyncio.TimeoutError:
                raise StreamDisconnected(
                    f"[{self.ctx.creator_id}] Chat stream produced no messages within 10s (chat_id={chat_id})"
                )
            except StopAsyncIteration:
                raise StreamDisconnected(
                    f"[{self.ctx.creator_id}] Chat stream closed before first message (chat_id={chat_id})"
                )

            async def _handle_ingest(msg):
                nonlocal total_messages, first_logged
                total_messages += 1
                if not first_logged:
                    log.info(
                        f"[{self.ctx.creator_id}] First chat message: {msg.get('user_name') or msg.get('username')}: {msg.get('text')}"
                    )
                    runtime_state.record_rumble_chat_status(
                        chat_id=chat_id,
                        status="CONNECTED",
                        error=None,
                    )
                    first_logged = True
                await self._handle_message_record(msg)

            await _handle_ingest(first_message)

            async for msg in stream:
                await _handle_ingest(msg)
        finally:
            log.info(
                f"[{self.ctx.creator_id}] Chat stream closed after ingesting {total_messages} messages"
            )
            try:
                await stream.aclose()
            except Exception:
                pass
            await client.aclose()

    # ------------------------------------------------------------

    async def _handle_message_record(self, msg: Dict[str, Any]) -> None:
        created_raw = msg.get("created_on") or msg.get("created_at") or msg.get("timestamp")
        if created_raw is None:
            created_raw = _utc_now().isoformat()

        created_raw_str = str(created_raw)

        key = (msg.get("user_id") or msg.get("username"), msg.get("text"), created_raw_str)
        if key in self._seen:
            return
        self._seen.add(key)

        created_ts = _parse_created_on(created_raw)
        if not created_ts:
            created_ts = _utc_now()

        # HARD RULE: ignore anything at/before baseline cutoff
        if self._baseline_cutoff and created_ts <= self._baseline_cutoff:
            return

        user = (msg.get("user_name") or msg.get("username") or "").strip()
        text = (msg.get("text") or "").strip()
        if not user or not text:
            return

        self_identities = {self.ctx.display_name.lower(), self.ctx.creator_id.lower()}
        is_self = user.lower() in self_identities

        log.info(f"💬 {user}: {text} (created_on={created_raw_str})")

        if not is_self:
            # Trigger evaluation
            await self._handle_triggers(user=user, text=text)

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
