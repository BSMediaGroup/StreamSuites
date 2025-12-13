import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, Response, WebSocket

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")

ROOM_RE = re.compile(r'(?:roomId|chatRoomId)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
POST_RE = re.compile(r'(?:postPath|chatPostPath)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)


class RumbleBrowserClient:
    """
    Persistent browser client (Cloudflare-safe) using a persistent profile.
    Extracts livestream chat session metadata via:
      - XHR/FETCH responses (bytes -> safe decode -> regex + JSON walk)
      - Document HTML (page.content) (regex)
      - WebSocket URLs + frames (regex + JSON walk)

    This is intentionally defensive: it must never crash the runtime.
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._lock = asyncio.Lock()

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        # room_id -> session dict
        self._sessions: Dict[str, dict] = {}

        # Prevent duplicate websocket hooks
        self._ws_hooked = set()

        # For throttling DOM scans
        self._last_dom_scan_at = 0.0

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------

    async def start(self):
        async with self._lock:
            if self._context and self._page:
                return

            log.info("Starting persistent Chromium browser (Cloudflare-safe)")

            self._playwright = await async_playwright().start()

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
            )

            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()

            # Hooks
            self._page.on("response", self._on_response)
            self._page.on("websocket", self._on_websocket)

    async def navigate(self, url: str):
        await self.start()
        if not self._page:
            raise RuntimeError("Browser page not initialized")

        log.debug(f"Browser fetching: {url}")

        # domcontentloaded is safer under CF; networkidle can hang
        await self._page.goto(url, wait_until="domcontentloaded")

        # Small wait to allow initial scripts to execute
        await self._page.wait_for_timeout(1500)

        # Immediately attempt a DOM scan as a fallback (some pages embed values)
        await self._scan_dom_for_chat_keys(force=True)

    async def get_page(self, url: str) -> Page:
        """
        Back-compat helper used by older modules.
        """
        await self.navigate(url)
        if not self._page:
            raise RuntimeError("Browser page not initialized")
        return self._page

    def clear_sessions(self):
        self._sessions.clear()

    def get_latest_session(self) -> Optional[dict]:
        if not self._sessions:
            return None
        return max(self._sessions.values(), key=lambda s: s["detected_at"])

    async def shutdown(self):
        async with self._lock:
            log.info("Shutting down persistent Chromium browser")

            try:
                # If the user manually closed the window, these may already be dead.
                if self._context:
                    await self._context.close()
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                log.warning(f"Browser shutdown error ignored: {e}")
            finally:
                self._context = None
                self._page = None
                self._playwright = None
                self._sessions.clear()
                self._ws_hooked.clear()
                self._last_dom_scan_at = 0.0

    # ---------------------------------------------------------------------
    # Hooks: Response
    # ---------------------------------------------------------------------

    async def _on_response(self, response: Response):
        """
        Only attempt body extraction for:
          - xhr/fetch/doc
        and only if content-length seems reasonable.
        """
        try:
            req = response.request
            rtype = req.resource_type if req else None
            if rtype not in ("xhr", "fetch", "document"):
                return

            # Headers can be missing; be defensive.
            headers = {}
            try:
                headers = response.headers or {}
            except Exception:
                headers = {}

            content_type = (headers.get("content-type") or "").lower()

            # Avoid chewing through huge binaries
            # (We can't always trust content-length, but if present, use it.)
            cl = headers.get("content-length")
            if cl:
                try:
                    if int(cl) > 2_000_000:
                        return
                except Exception:
                    pass

            # Read bytes first (safe for binary)
            try:
                body = await response.body()
            except Exception as e:
                # Very common with certain resources; just ignore.
                log.debug(f"Ignoring response body read error: {e}")
                return

            if not body:
                return

            # Decode safely
            text = self._safe_decode(body)

            # Fast regex scan
            rid, ppath = self._find_chat_keys_text(text)
            if rid and ppath:
                self._store_session(rid, ppath, source=response.url, kind=f"response-{rtype}-regex")
                return

            # If it claims to be JSON or looks like JSON, try parse and walk.
            if "json" in content_type or text.lstrip().startswith(("{", "[")):
                data = None
                try:
                    data = json.loads(text)
                except Exception:
                    data = None

                if data is not None:
                    rid2, ppath2 = self._find_chat_keys_json(data)
                    if rid2 and ppath2:
                        self._store_session(rid2, ppath2, source=response.url, kind=f"response-{rtype}-json")
                        return

            # Occasionally the page embeds things late; throttle DOM scan a bit
            await self._scan_dom_for_chat_keys()

        except Exception as e:
            # Never crash the event loop for logging
            log.debug(f"Ignoring response parse error: {e}")

    # ---------------------------------------------------------------------
    # Hooks: WebSocket
    # ---------------------------------------------------------------------

    def _on_websocket(self, ws: WebSocket):
        try:
            ws_url = ws.url or ""
            if ws_url in self._ws_hooked:
                return
            self._ws_hooked.add(ws_url)

            log.debug(f"WebSocket opened: {ws_url}")

            # URL scan (rare but cheap)
            rid, ppath = self._find_chat_keys_text(ws_url)
            if rid and ppath:
                self._store_session(rid, ppath, source=ws_url, kind="ws-url")

            ws.on("framereceived", lambda frame: asyncio.create_task(self._on_ws_frame(ws_url, frame)))
            ws.on("framesent", lambda frame: asyncio.create_task(self._on_ws_frame(ws_url, frame)))

        except Exception as e:
            log.debug(f"Ignoring websocket hook error: {e}")

    async def _on_ws_frame(self, ws_url: str, frame: Any):
        try:
            payload = None

            if isinstance(frame, str):
                payload = frame
            elif isinstance(frame, dict):
                payload = frame.get("payload")
            else:
                payload = str(frame)

            if not payload:
                return

            # Regex scan
            rid, ppath = self._find_chat_keys_text(str(payload))
            if rid and ppath:
                self._store_session(rid, ppath, source=ws_url, kind="ws-frame-regex")
                return

            # JSON scan (if plausible)
            s = str(payload).lstrip()
            if s.startswith(("{", "[")):
                try:
                    data = json.loads(payload)
                except Exception:
                    return

                rid2, ppath2 = self._find_chat_keys_json(data)
                if rid2 and ppath2:
                    self._store_session(rid2, ppath2, source=ws_url, kind="ws-frame-json")

        except Exception as e:
            log.debug(f"Ignoring websocket frame parse error: {e}")

    # ---------------------------------------------------------------------
    # DOM fallback scan
    # ---------------------------------------------------------------------

    async def _scan_dom_for_chat_keys(self, force: bool = False):
        """
        Some Rumble pages embed these keys in inline scripts or DOM attributes.
        Scan page HTML occasionally.
        """
        try:
            if not self._page:
                return

            now = time.time()
            if not force and (now - self._last_dom_scan_at) < 3.0:
                return
            self._last_dom_scan_at = now

            html = await self._page.content()
            if not html:
                return

            rid, ppath = self._find_chat_keys_text(html)
            if rid and ppath:
                self._store_session(rid, ppath, source="page.content()", kind="dom-regex")

        except Exception:
            return

    # ---------------------------------------------------------------------
    # Extraction helpers
    # ---------------------------------------------------------------------

    def _safe_decode(self, b: bytes) -> str:
        """
        Decode bytes without throwing.
        """
        try:
            return b.decode("utf-8", errors="ignore")
        except Exception:
            try:
                return b.decode("latin-1", errors="ignore")
            except Exception:
                return ""

    def _find_chat_keys_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            if not text:
                return None, None

            room = None
            post = None

            m1 = ROOM_RE.search(text)
            if m1:
                room = m1.group(1)

            m2 = POST_RE.search(text)
            if m2:
                post = m2.group(1)

            return room, post
        except Exception:
            return None, None

    def _find_chat_keys_json(self, obj: Any) -> Tuple[Optional[str], Optional[str]]:
        room_id = None
        post_path = None

        def walk(x: Any):
            nonlocal room_id, post_path
            if room_id and post_path:
                return

            if isinstance(x, dict):
                if room_id is None:
                    v = x.get("roomId") or x.get("chatRoomId")
                    if isinstance(v, str) and v.strip():
                        room_id = v.strip()

                if post_path is None:
                    v = x.get("postPath") or x.get("chatPostPath")
                    if isinstance(v, str) and v.strip():
                        post_path = v.strip()

                for vv in x.values():
                    walk(vv)

            elif isinstance(x, list):
                for item in x:
                    walk(item)

        walk(obj)
        return room_id, post_path

    def _store_session(self, room_id: str, post_path: str, source: str, kind: str):
        session_id = str(room_id)
        if session_id in self._sessions:
            return

        self._sessions[session_id] = {
            "room_id": str(room_id),
            "post_path": str(post_path),
            "detected_at": time.time(),
            "source_url": source,
            "kind": kind,
        }

        log.info(f"Discovered livestream chat session: room={room_id} ({kind})")
