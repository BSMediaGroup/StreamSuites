import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, Response, WebSocket

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")

ROOM_RE = re.compile(
    r'(?:roomId|chatRoomId|room_id)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
POST_RE = re.compile(
    r'(?:postPath|chatPostPath|post_path)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)


class RumbleBrowserClient:
    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._lock = asyncio.Lock()

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._sessions: Dict[str, dict] = {}
        self._ws_hooked = set()

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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

            self._page.on("response", self._on_response)
            self._page.on("websocket", self._on_websocket)

    async def navigate(self, url: str):
        await self.start()
        log.debug(f"Browser fetching: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")
        await self._page.wait_for_timeout(2000)

    async def get_page(self, url: str) -> Page:
        await self.navigate(url)
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

    # ------------------------------------------------------------------
    # Socket.IO POLLING (CRITICAL)
    # ------------------------------------------------------------------

    async def _on_response(self, response: Response):
        try:
            url = response.url or ""
            if "/socket.io/" not in url:
                return

            body = await response.body()
            if not body:
                return

            text = body.decode("utf-8", errors="ignore").strip()
            if not text:
                return

            # Socket.IO event frame: 42["init",{...}]
            if text.startswith("42"):
                try:
                    payload = json.loads(text[2:])
                except Exception:
                    return

                if isinstance(payload, list) and len(payload) >= 2:
                    event, data = payload[0], payload[1]
                    if event == "init" and isinstance(data, dict):
                        room = data.get("room_id")
                        post = data.get("post_path")
                        if room and post:
                            self._store_session(room, post, url, "socketio-polling-init")
                            return

            # Fallback regex scan (some responses inline it)
            rid, ppath = self._find_chat_keys_text(text)
            if rid and ppath:
                self._store_session(rid, ppath, url, "socketio-polling-regex")

        except Exception as e:
            log.debug(f"Ignoring socket.io response parse error: {e}")

    # ------------------------------------------------------------------
    # WebSocket (OPTIONAL UPGRADE PATH)
    # ------------------------------------------------------------------

    def _on_websocket(self, ws: WebSocket):
        try:
            if ws.url in self._ws_hooked:
                return

            self._ws_hooked.add(ws.url)
            log.debug(f"WebSocket opened: {ws.url}")

            ws.on("framereceived", lambda f: asyncio.create_task(self._on_ws_frame(ws.url, f)))
            ws.on("framesent", lambda f: asyncio.create_task(self._on_ws_frame(ws.url, f)))

        except Exception as e:
            log.debug(f"Ignoring websocket hook error: {e}")

    async def _on_ws_frame(self, ws_url: str, frame: Any):
        try:
            payload = None

            if isinstance(frame, str):
                payload = frame
            elif isinstance(frame, dict):
                payload = frame.get("payload")
            elif hasattr(frame, "payload"):
                payload = frame.payload
            else:
                payload = str(frame)

            if not payload:
                return

            s = str(payload).strip()

            # Socket.IO framed WS message
            if s.startswith("42"):
                try:
                    data = json.loads(s[2:])
                except Exception:
                    return

                if isinstance(data, list) and len(data) >= 2:
                    event, d = data[0], data[1]
                    if event == "init" and isinstance(d, dict):
                        room = d.get("room_id")
                        post = d.get("post_path")
                        if room and post:
                            self._store_session(room, post, ws_url, "ws-socketio-init")
                            return

            # Generic JSON scan
            try:
                obj = json.loads(s)
            except Exception:
                obj = None

            if obj:
                rid, ppath = self._find_chat_keys_json(obj)
                if rid and ppath:
                    self._store_session(rid, ppath, ws_url, "ws-json")
                    return

            # Regex fallback
            rid, ppath = self._find_chat_keys_text(s)
            if rid and ppath:
                self._store_session(rid, ppath, ws_url, "ws-regex")

        except Exception as e:
            log.debug(f"Ignoring websocket frame parse error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_chat_keys_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None
        r = ROOM_RE.search(text)
        p = POST_RE.search(text)
        return (r.group(1) if r else None, p.group(1) if p else None)

    def _find_chat_keys_json(self, obj: Any) -> Tuple[Optional[str], Optional[str]]:
        room = None
        post = None

        def walk(x):
            nonlocal room, post
            if room and post:
                return
            if isinstance(x, dict):
                room = room or x.get("room_id") or x.get("roomId") or x.get("chatRoomId")
                post = post or x.get("post_path") or x.get("postPath") or x.get("chatPostPath")
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for i in x:
                    walk(i)

        walk(obj)
        return room, post

    def _store_session(self, room_id: str, post_path: str, source: str, kind: str):
        if room_id in self._sessions:
            return

        self._sessions[room_id] = {
            "room_id": room_id,
            "post_path": post_path,
            "detected_at": time.time(),
            "source_url": source,
            "kind": kind,
        }

        log.info(f"Discovered livestream chat session: room={room_id} ({kind})")
