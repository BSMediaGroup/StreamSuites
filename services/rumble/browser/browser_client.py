import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent Playwright Chromium client.
    Uses a real browser profile so Cloudflare clears once and stays cleared.
    """

    _instance: Optional["RumbleBrowserClient"] = None

    PROFILE_DIR = Path(".browser/rumble")

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        if self._context:
            return

        log.info("Starting persistent Chromium browser (Cloudflare-safe)")

        self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        # IMPORTANT: headless=False + persistent profile
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.PROFILE_DIR),
            headless=False,   # REQUIRED for Cloudflare
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled"
            ],
        )

        self._page = await self._context.new_page()

    async def fetch_html(self, url: str) -> str:
        async with self._lock:
            if not self._context or not self._page:
                await self.start()

            log.debug(f"Browser fetching: {url}")

            await self._page.goto(
                url,
                wait_until="load",
                timeout=60000
            )

            # Give Cloudflare time if needed
            await asyncio.sleep(2)

            return await self._page.content()

    async def shutdown(self):
        log.info("Shutting down persistent Chromium browser")

        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        finally:
            self._context = None
            self._playwright = None
            self._page = None
