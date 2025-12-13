import asyncio
import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from playwright.async_api import async_playwright, BrowserContext, Page, WebSocket

from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    Persistent Chromium browser (Cloudflare-safe).

    AUTHORITATIVE RESPONSIBILITIES:
      - Maintain logged-in Rumble session
      - Navigate to livestream watch page
      - Own the chat WebSocket
      - Emit chat messages to subscribers
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._lock = asyncio.Lock()

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._chat_listeners: list[Callable[[dict], None]] = []
        self._ws_hooked = set()

    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, watch_url: str) -> None:
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

            self._page.on("websocket", self._on_websocket)

            log.info("Initializing Rumble session in browser")
            await self._page.goto(watch_url, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(3000)

            await self._log_cookie_state()

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
                self._ws_hooked.clear()
                self._chat_listeners.clear()

    # ------------------------------------------------------------------
    # Cookie diagnostics (debug only)
    # ------------------------------------------------------------------

    async def _log_cookie_state(self):
        try:
            cookies = await self._context.cookies()
            names = sorted(c["name"] for c in cookies if "rumble" in c.get("domain", ""))
            log.warning(f"RUMBLE COOKIES PRESENT: {', '.join(names)}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Chat subscription
    # ------------------------------------------------------------------

    def subscribe_chat(self, callback: Callable[[dict], None]) -> None:
        self._chat_listeners.append(callback)

    # ------------------------------------------------------------------
    # WebSocket handling
    # ------------------------------------------------------------------

    def _on_websocket(self, ws: WebSocket):
        try:
            if ws.url in self._ws_hooked:
                return

            self._ws_hooked.add(ws.url)
            log.info(f"Chat WebSocket connected: {ws.url}")

            ws.on("framereceived", lambda f: asyncio.create_task(self._handle_frame(f)))
        except Exception as e:
            log.error(f"WebSocket hook error: {e}")

    async def _handle_frame(self, frame):
        try:
            payload = frame if isinstance(frame, str) else getattr(frame, "payload", None)
            if not payload:
                return

            if not payload.strip().startswith("{"):
                return

            data = json.loads(payload)

            # Rumble chat messages arrive inside message events
            msg = data.get("data") or data.get("message")
            if not isinstance(msg, dict):
                return

            for cb in self._chat_listeners:
                cb(msg)

        except Exception:
            # NEVER crash browser loop
            return
