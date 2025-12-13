import asyncio
import json
import time
from typing import Dict, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Response

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Singleton persistent browser used to:
    - bypass Cloudflare
    - intercept network responses
    - discover livestream chat bootstrap data
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # livestream_id -> session data
        self._sessions: Dict[str, dict] = {}

        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        async with self._lock:
            if self._browser:
                return

            log.info("Starting persistent Chromium browser (Cloudflare-safe)")

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

            # Attach network interception
            self._page.on("response", self._on_response)

    async def navigate(self, url: str):
        await self.start()

        if not self._page:
            raise RuntimeError("Browser page not initialized")

        log.debug(f"Browser fetching: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")

    def get_latest_session(self) -> Optional[dict]:
        """
        Return the most recently discovered livestream session.
        """
        if not self._sessions:
            return None

        return max(self._sessions.values(), key=lambda s: s["detected_at"])

    async def shutdown(self):
        async with self._lock:
            log.info("Shutting down persistent Chromium browser")

            try:
                if self._context:
                    await self._context.close()
                if self._browser:
                    await self._browser.close()
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                log.warning(f"Browser shutdown error ignored: {e}")
            finally:
                self._browser = None
                self._context = None
                self._page = None
                self._playwright = None
                self._sessions.clear()

    async def _on_response(self, response: Response):
        """
        Intercept network responses and look for chat bootstrap payloads.
        """
        try:
            url = response.url

            # Only JSON responses are interesting
            if "application/json" not in (response.headers.get("content-type") or ""):
                return

            text = await response.text()
            data = json.loads(text)

            # Heuristic: chat bootstrap payload
            room_id = (
                data.get("roomId")
                or data.get("chatRoomId")
                or data.get("data", {}).get("roomId")
            )

            post_path = (
                data.get("postPath")
                or data.get("chatPostPath")
                or data.get("data", {}).get("postPath")
            )

            if not room_id or not post_path:
                return

            session_id = str(room_id)

            if session_id in self._sessions:
                return

            self._sessions[session_id] = {
                "room_id": room_id,
                "post_path": post_path,
                "detected_at": time.time(),
                "source_url": url,
            }

            log.info(
                f"Discovered livestream chat session: room={room_id}"
            )

        except Exception as e:
            log.debug(f"Ignoring response parse error: {e}")
