import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.async_api import async_playwright, BrowserContext, Page, Response

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent browser client that:
    - survives Cloudflare better via a persistent profile
    - allows you to log in once and stay logged in
    - intercepts JSON responses and extracts chat bootstrap data robustly
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # room_id -> session
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

            # TRUE persistent context: keeps login/session between runs
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
            )

            # Use an existing page or create one
            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()

            # Attach interception
            self._page.on("response", self._on_response)

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
                # This must NEVER crash shutdown
                log.warning(f"Browser shutdown error ignored: {e}")
            finally:
                self._context = None
                self._page = None
                self._playwright = None
                self._sessions.clear()

    # ----------------------------
    # Interception + extraction
    # ----------------------------

    async def _on_response(self, response: Response):
        """
        Intercept JSON responses and try to extract chat bootstrap data.
        Robust to list/None/dict JSON shapes.
        """
        try:
            ct = (response.headers.get("content-type") or "").lower()
            if "application/json" not in ct:
                return

            # Some responses can't provide bodies; ignore safely
            try:
                body_text = await response.text()
            except Exception as e:
                log.debug(f"Ignoring response body read error: {e}")
                return

            if not body_text:
                return

            try:
                data = json.loads(body_text)
            except Exception:
                return

            room_id, post_path = self._find_chat_keys(data)

            if not room_id or not post_path:
                return

            session_id = str(room_id)
            if session_id in self._sessions:
                return

            self._sessions[session_id] = {
                "room_id": room_id,
                "post_path": post_path,
                "detected_at": time.time(),
                "source_url": response.url,
            }

            log.info(f"Discovered livestream chat session: room={room_id}")

        except Exception as e:
            # Never allow interception to kill the runtime
            log.debug(f"Ignoring response parse error: {e}")

    def _find_chat_keys(self, obj: Any) -> Tuple[Optional[str], Optional[str]]:
        """
        Walk arbitrary JSON and return (room_id, post_path) if found.

        We look for common key variants seen across Rumble payloads:
        - roomId / chatRoomId
        - postPath / chatPostPath
        """
        room_id = None
        post_path = None

        def walk(x: Any):
            nonlocal room_id, post_path

            if room_id and post_path:
                return

            if isinstance(x, dict):
                # direct hits
                if room_id is None:
                    v = x.get("roomId") or x.get("chatRoomId")
                    if isinstance(v, str) and v.strip():
                        room_id = v.strip()

                if post_path is None:
                    v = x.get("postPath") or x.get("chatPostPath")
                    if isinstance(v, str) and v.strip():
                        post_path = v.strip()

                # continue walk
                for vv in x.values():
                    walk(vv)

            elif isinstance(x, list):
                for item in x:
                    walk(item)

        walk(obj)
        return room_id, post_path
