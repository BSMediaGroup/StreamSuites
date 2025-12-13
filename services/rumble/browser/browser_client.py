import asyncio
import time
from pathlib import Path
from typing import Dict, Optional

from playwright.async_api import async_playwright, BrowserContext, Page

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent Chromium browser (Cloudflare-safe) using a persistent profile.

    Purpose (now):
      - Keep a logged-in Rumble session alive across runs
      - Provide fresh cookies to REST clients (httpx) so you DO NOT manage cookies in .env

    Notes:
      - Uses launch_persistent_context(user_data_dir=...)
      - headless=False so you can see/log-in once, then it stays logged in
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._lock = asyncio.Lock()

        # Persistent profile directory (this is where login state lives)
        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        # For throttling navigation
        self._last_nav_at = 0.0

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ---------------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------------

    async def start(self) -> None:
        async with self._lock:
            if self._context and self._page:
                return

            log.info("Starting persistent Chromium browser (Cloudflare-safe)")

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

            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()

    async def shutdown(self) -> None:
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

    # ---------------------------------------------------------------------
    # Navigation (optional helper)
    # ---------------------------------------------------------------------

    async def navigate(self, url: str, min_interval_sec: float = 2.0) -> None:
        """
        Navigate the persistent page. This is optional for cookie harvesting,
        but useful if you want to ensure Cloudflare clearance is refreshed.
        """
        await self.start()
        if not self._page:
            raise RuntimeError("Browser page not initialized")

        now = time.time()
        if (now - self._last_nav_at) < min_interval_sec:
            return
        self._last_nav_at = now

        log.debug(f"Browser fetching: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")
        await self._page.wait_for_timeout(1500)

    async def get_page(self) -> Page:
        await self.start()
        if not self._page:
            raise RuntimeError("Browser page not initialized")
        return self._page

    # ---------------------------------------------------------------------
    # Cookie export (THIS is the key piece)
    # ---------------------------------------------------------------------

    async def get_cookie_dict_for(self, domain_substr: str = "rumble.com") -> Dict[str, str]:
        """
        Return cookies from the persistent context as a dict usable by httpx.
        This keeps your bot working even when cf_clearance/__cf_bm rotate.
        """
        await self.start()
        if not self._context:
            return {}

        try:
            cookies = await self._context.cookies()
        except Exception as e:
            log.warning(f"Failed to read browser cookies: {e}")
            return {}

        out: Dict[str, str] = {}
        for c in cookies:
            dom = (c.get("domain") or "").lstrip(".")
            if domain_substr in dom:
                name = c.get("name")
                val = c.get("value")
                if name and val:
                    out[name] = val

        return out
