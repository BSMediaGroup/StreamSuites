import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    async def _ensure_browser(self):
        async with self._lock:
            if self._browser and self._context:
                return

            log.info("Starting persistent Chromium browser (Cloudflare-safe)")

            self._playwright = await async_playwright().start()

            self._browser = await self._playwright.chromium.launch(
                headless=False,  # MUST be visible for Cloudflare
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                ],
            )

            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

    async def get_page(self, url: str) -> Page:
        """
        Ensure browser is running, open a new page,
        navigate to the URL, and return the page.
        """
        await self._ensure_browser()

        assert self._context is not None

        page = await self._context.new_page()

        log.debug(f"Browser fetching: {url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        return page

    async def shutdown(self):
        async with self._lock:
            log.info("Shutting down persistent Chromium browser")

            try:
                if self._context:
                    await self._context.close()
            except Exception:
                pass

            try:
                if self._browser:
                    await self._browser.close()
            except Exception:
                pass

            try:
                if self._playwright:
                    await self._playwright.stop()
            except Exception:
                pass

            self._context = None
            self._browser = None
            self._playwright = None
