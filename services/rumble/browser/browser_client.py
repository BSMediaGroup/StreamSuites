import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Singleton Playwright Chromium client that can pass Cloudflare
    and return the FINAL rendered HTML.
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        if self._browser:
            return

        log.info("Starting Playwright Chromium browser")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True
        )

        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        self._page = await context.new_page()

    async def fetch_html(self, url: str) -> str:
        async with self._lock:
            if not self._browser or not self._page:
                await self.start()

            log.debug(f"Browser fetching: {url}")

            # Navigate and let Cloudflare do its thing
            await self._page.goto(
                url,
                wait_until="load",
                timeout=60000
            )

            # Give Cloudflare JS time to complete redirect (critical)
            await asyncio.sleep(3)

            return await self._page.content()

    async def shutdown(self):
        log.info("Shutting down Playwright browser")

        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            log.error(f"Error shutting down browser: {e}")
        finally:
            self._browser = None
            self._playwright = None
            self._page = None
