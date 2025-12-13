import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any, List

from playwright.async_api import async_playwright, BrowserContext, Page, Response

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent Chromium browser that:
      - Owns Rumble authentication
      - Stays open
      - Intercepts Socket.IO polling responses
      - Emits decoded chat messages
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        self._chat_callbacks: List[Callable[[dict], None]] = []
        self._started = False

    # ------------------------------------------------------------

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------

    async def start(self, watch_url: str) -> None:
        async with self._lock:
            if self._started:
                return

            log.info("Starting persistent Chromium browser (Socket.IO interception mode)")

            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
                viewport={"width": 1280, "height": 800},
            )

            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            # Hook network responses (THIS IS THE KEY)
            self._page.on("response", self._on_response)

            log.info(f"Navigating browser to watch page → {watch_url}")
            await self._page.goto(watch_url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(5000)

            cookies = await self.get_cookie_dict_for("rumble.com")
            if cookies:
                log.warning("RUMBLE COOKIES PRESENT: " + ", ".join(sorted(cookies.keys())))

            self._started = True

    # ------------------------------------------------------------

    async def shutdown(self) -> None:
        async with self._lock:
            try:
                if self._context:
                    await self._context.close()
                if self._playwright:
                    await self._playwright.stop()
            finally:
                self._context = None
                self._page = None
                self._playwright = None
                self._started = False

    # ------------------------------------------------------------

    async def get_cookie_dict_for(self, domain_substr: str) -> Dict[str, str]:
        if not self._context:
            return {}

        cookies = await self._context.cookies()
        out: Dict[str, str] = {}

        for c in cookies:
            domain = (c.get("domain") or "").lstrip(".")
            if domain_substr in domain:
                if c.get("name") and c.get("value"):
                    out[c["name"]] = c["value"]

        return out

    # ------------------------------------------------------------
    # Chat subscription
    # ------------------------------------------------------------

    def subscribe_chat(self, callback: Callable[[dict], None]) -> None:
        if callback not in self._chat_callbacks:
            self._chat_callbacks.append(callback)

    # ------------------------------------------------------------
    # Socket.IO polling interception (THE IMPORTANT PART)
    # ------------------------------------------------------------

    def _on_response(self, response: Response) -> None:
        url = response.url

        if "socket.io" not in url or "transport=polling" not in url:
            return

        asyncio.create_task(self._handle_socketio_response(response))

    async def _handle_socketio_response(self, response: Response) -> None:
        try:
            text = await response.text()
        except Exception:
            return

        # Socket.IO packets are newline separated
        for line in text.splitlines():
            if not line.startswith("42"):
                continue

            try:
                payload = json.loads(line[2:])
            except Exception:
                continue

            if not isinstance(payload, list) or len(payload) < 2:
                continue

            event, data = payload[0], payload[1]

            if event != "message" or not isinstance(data, dict):
                continue

            for cb in self._chat_callbacks:
                try:
                    cb(data)
                except Exception:
                    pass
