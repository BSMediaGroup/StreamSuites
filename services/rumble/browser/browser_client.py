import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any

from playwright.async_api import async_playwright, BrowserContext, Page, WebSocket

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent Chromium browser (Cloudflare-safe).

    RESPONSIBILITIES:
      - Own authentication state (login, CF clearance, session cookies)
      - Stay open for the lifetime of the bot
      - Expose fresh cookies to REST clients
      - Tap into Rumble chat WebSocket traffic

    THIS CLASS IS AUTHORITATIVE FOR AUTH.
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._lock = asyncio.Lock()

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._last_nav_at = 0.0

        # Chat subscribers
        self._chat_callbacks: list[Callable[[dict], None]] = []

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, watch_url: Optional[str] = None) -> None:
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

            # 🔥 Hook ALL websockets
            self._page.on("websocket", self._on_websocket)

            if watch_url:
                await self.navigate(watch_url)

            cookies = await self.get_cookie_dict_for("rumble.com")
            if cookies:
                log.warning(
                    "RUMBLE COOKIES PRESENT: " + ", ".join(sorted(cookies.keys()))
                )

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

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate(self, url: str, min_interval_sec: float = 2.0) -> None:
        if not self._page:
            return

        now = time.time()
        if (now - self._last_nav_at) < min_interval_sec:
            return

        self._last_nav_at = now

        log.info(f"Initializing Rumble session in browser → {url}")
        await self._page.goto(url, wait_until="domcontentloaded")
        await self._page.wait_for_timeout(3000)

    # ------------------------------------------------------------------
    # Cookie export
    # ------------------------------------------------------------------

    async def get_cookie_dict_for(self, domain_substr: str = "rumble.com") -> Dict[str, str]:
        if not self._context:
            return {}

        try:
            cookies = await self._context.cookies()
        except Exception as e:
            log.error(f"Failed to read cookies: {e}")
            return {}

        out: Dict[str, str] = {}
        for c in cookies:
            domain = (c.get("domain") or "").lstrip(".")
            if domain_substr in domain:
                name = c.get("name")
                val = c.get("value")
                if name and val:
                    out[name] = val

        return out

    # ------------------------------------------------------------------
    # WebSocket handling
    # ------------------------------------------------------------------

    def subscribe_chat(self, callback: Callable[[dict], None]) -> None:
        if callback not in self._chat_callbacks:
            self._chat_callbacks.append(callback)

    def _on_websocket(self, ws: WebSocket) -> None:
        url = ws.url or ""
        log.info(f"WebSocket opened: {url}")

        ws.on("framereceived", lambda payload: asyncio.create_task(
            self._handle_ws_frame(payload)
        ))

    async def _handle_ws_frame(self, payload: Any) -> None:
        try:
            # Playwright gives BYTES or STR — not dicts
            if isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="ignore")
            elif isinstance(payload, str):
                text = payload
            else:
                return

            # 🔥 TEMPORARY RAW FRAME LOG
            log.debug(f"WS FRAME: {text[:500]}")

            if not text.startswith("{"):
                return

            data = json.loads(text)

            # Pass through anything that looks like chat
            if isinstance(data, dict) and "text" in data and "user" in data:
                for cb in self._chat_callbacks:
                    try:
                        cb(data)
                    except Exception:
                        pass

        except Exception as e:
            log.error(f"WS frame parse error: {e}")
