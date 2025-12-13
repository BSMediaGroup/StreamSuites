import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, Response, WebSocket

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")

ROOM_RE = re.compile(r'(?:roomId|chatRoomId)"?\s*[:=]\s*"([^"]+)"', re.IGNORECASE)
POST_RE = re.compile(r'(?:postPath|chatPostPath)"?\s*[:=]\s*"([^"]+)"', re.IGNORECASE)


class RumbleBrowserClient:
    """
    Persistent browser client that:
    - survives Cloudflare better via a persistent profile
    - allows you to log in once and stay logged in
    - extracts chat bootstrap data from:
        (a) XHR/fetch response bodies (any JSON-ish content type)
        (b) WebSocket URLs / frames (common for chat)
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # session_id -> session dict
        self._sessions: Dict[str, dict] = {}

        self._lock = asyncio.Lock()

        # Persistent profile directory (kept out of git via .gitignore)
        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

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

            # Attach listeners
            self._page.on("response", self._on_response)
            self._page.on("websocket", self._on_websocket)

    async def navigate(self, url: str):
        await self.start()
        if not self._page:
            raise RuntimeError("Browser page not initialized")

        log.debug(f"Browser fetching: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")

    def get_latest_session(self) -> Optional[dict]:
        if not self._sessions:
            return None
        return max(self._sessions.values(), key=lambda s: s["detected_at"])

    def clear_sessions(self):
        self._sessions.clear()

    async def shutdown(self):
        async with self._lock:
            log.info("Shutting down persistent Chromium browser")

            try:
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

    # ----------------------------
    # Response extraction
    # ----------------------------

    async def _on_response(self, response: Response):
        """
        Try to parse response bodies for chat keys.

        We DO NOT rely on content-type == application/json.
        We instead focus on fetch/xhr resources because those are likely API payloads.
        """
        try:
            req = response.request
            rtype = req.resource_type if req else None
            if rtype not in ("xhr", "fetch"):
                return

            # Some responses will not have bodies accessible; ignore quietly.
            try:
                body_text = await response.text()
            except Exception as e:
                log.debug(f"Ignoring response body read error: {e}")
                return

            if not body_text:
                return

            # Fast-path: regex scan before attempting JSON parse
            rid, ppath = self._find_chat_keys_text(body_text)
            if rid and ppath:
                self._store_session(rid, ppath, source=response.url, kind="response-regex")
                return

            # If it looks like JSON, attempt parsing
            body_strip = body_text.lstrip()
            if not (body_strip.startswith("{") or body_strip.startswith("[")):
                return

            try:
                data = json.loads(body_text)
            except Exception:
                return

            rid2, ppath2 = self._find_chat_keys_json(data)
            if rid2 and ppath2:
                self._store_session(rid2, ppath2, source=response.url, kind="response-json")

        except Exception as e:
            log.debug(f"Ignoring response parse error: {e}")

    # ----------------------------
    # WebSocket extraction
    # ----------------------------

    def _on_websocket(self, ws: WebSocket):
        """
        WebSocket handler is sync. We attach frame listeners and parse URLs/frames.
        """
        try:
            url = ws.url or ""
            # Try extracting from URL immediately (sometimes roomId appears here)
            rid, ppath = self._find_chat_keys_text(url)
            if rid and ppath:
                self._store_session(rid, ppath, source=url, kind="ws-url")

            ws.on("framereceived", lambda frame: asyncio.create_task(self._on_ws_frame(url, frame)))
            ws.on("framesent", lambda frame: asyncio.create_task(self._on_ws_frame(url, frame)))
        except Exception as e:
            log.debug(f"Ignoring websocket hook error: {e}")

    async def _on_ws_frame(self, ws_url: str, frame: Any):
        """
        Parse websocket frames. Frame may be text or binary.
        """
        try:
            payload = None

            # Playwright frame can be str or dict depending on version
            if isinstance(frame, str):
                payload = frame
            elif isinstance(frame, dict):
                payload = frame.get("payload")
            else:
                payload = str(frame)

            if not payload:
                return

            # 1) regex scan text
            rid, ppath = self._find_chat_keys_text(payload)
            if rid and ppath:
                self._store_session(rid, ppath, source=ws_url, kind="ws-frame-regex")
                return

            # 2) try json if possible
            s = str(payload).lstrip()
            if s.startswith("{") or s.startswith("["):
                try:
                    data = json.loads(payload)
                except Exception:
                    return

                rid2, ppath2 = self._find_chat_keys_json(data)
                if rid2 and ppath2:
                    self._store_session(rid2, ppath2, source=ws_url, kind="ws-frame-json")

        except Exception as e:
            log.debug(f"Ignoring websocket frame parse error: {e}")

    # ----------------------------
    # Key finding + storage
    # ----------------------------

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

    def _find_chat_keys_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Regex search for room/post keys in arbitrary text.
        """
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
        """
        Walk arbitrary JSON and return (room_id, post_path) if found.
        """
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
