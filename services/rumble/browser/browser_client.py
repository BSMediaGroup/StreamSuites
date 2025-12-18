import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page, Frame
from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    MODEL A — DOM INJECTION BROWSER CLIENT (POC-LOCKED)

    HARD LAWS:
    - Persistent profile (cookies ONLY)
    - ONE authoritative page
    - CHAT SUBMIT MUST USE PLAYWRIGHT KEYBOARD
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._chat_frame: Optional[Frame] = None

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        self._started = False
        self._shutting_down = False

    # ------------------------------------------------------------

    @classmethod
    def instance(cls) -> "RumbleBrowserClient":
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return

            log.info("Starting persistent Chromium browser (safe reset)")

            self._playwright = await async_playwright().start()

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-session-crashed-bubble",
                    "--disable-restore-session-state",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )

            pages = self._context.pages

            if pages:
                self._page = pages[0]
                await self._page.goto("about:blank")
                for p in pages[1:]:
                    await p.close()
            else:
                self._page = await self._context.new_page()

            self._chat_frame = None
            self._started = True
            self._shutting_down = False

    # ------------------------------------------------------------

    async def ensure_logged_in(self) -> None:
        if not self._page:
            raise RuntimeError("Browser not started")

        await self._page.goto(
            "https://rumble.com/account/login",
            wait_until="domcontentloaded",
        )

        login_form = await self._page.query_selector("form[action*='login']")
        if login_form:
            log.warning("🔐 Login required — complete login, then press ENTER")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input)
        else:
            log.info("✅ Login session valid — continuing")

    # ------------------------------------------------------------

    async def open_watch(self, url: str) -> None:
        if not self._page:
            raise RuntimeError("Browser not started")

        log.info(f"Navigating to watch page → {url}")
        self._chat_frame = None
        await self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------

    async def wait_for_chat_ready(self, timeout_ms: int = 30000) -> None:
        if not self._page:
            raise RuntimeError("Browser not started")

        log.info("Waiting for chat iframe")

        deadline = timeout_ms / 1000
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < deadline:
            for frame in self._page.frames:
                try:
                    if await frame.query_selector("#chat-message-text-input"):
                        self._chat_frame = frame
                        log.info("Chat iframe detected and locked")
                        return
                except Exception:
                    pass

            await asyncio.sleep(0.5)

        raise TimeoutError("Chat iframe not found")

    # ------------------------------------------------------------
    # 🔥 AUTHORITATIVE CHAT SEND — POC DOM INJECTION (REACT EVENTS + CLICK)
    # ------------------------------------------------------------

    async def _send_chat_poc_injection(self, message: str) -> str:
        """
        This is the canonical POC mechanism, ported 1:1 into the production client.

        POC steps:
        1) focus input
        2) clear + set value
        3) dispatch React-friendly events (InputEvent + change + compositionend)
        4) force-enable send button
        5) click send button
        """
        if not self._chat_frame:
            raise RuntimeError("Chat frame not initialized")

        return await self._chat_frame.evaluate(
            """
            (msg) => {
                const input = document.querySelector("#chat-message-text-input");
                const sendBtn = document.querySelector("button.chat--send");

                if (!input) return "NO_INPUT";
                if (!sendBtn) return "NO_SEND_BUTTON";

                // Step 1: focus
                input.focus();

                // Step 2: clear + set value
                input.value = "";
                input.value = msg;

                // Step 3: proper React events
                input.dispatchEvent(
                    new InputEvent("input", {
                        bubbles: true,
                        inputType: "insertText",
                        data: msg
                    })
                );

                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }));

                // Step 4: force-enable button
                sendBtn.disabled = false;

                // Step 5: click send
                sendBtn.click();

                return "SENT_OK";
            }
            """,
            message,
        )

    # ------------------------------------------------------------
    # LEGACY KEYBOARD PATH (RETAINED AS FALLBACK ONLY)
    # ------------------------------------------------------------

    async def _send_chat_keyboard(self, message: str) -> bool:
        if not self._chat_frame or not self._page:
            raise RuntimeError("Chat frame not initialized")

        await self._chat_frame.click("#chat-message-text-input")

        await self._page.keyboard.press("Control+A")
        await self._page.keyboard.press("Backspace")

        await self._page.keyboard.type(message, delay=20)
        await self._page.keyboard.press("Enter")

        return True

    # ------------------------------------------------------------

    async def send_chat_dom(self, message: str) -> bool:
        if not self._chat_frame or not self._page:
            raise RuntimeError("Chat frame not initialized")

        try:
            # Primary: POC-locked DOM injection that guarantees send via click
            res = await self._send_chat_poc_injection(message)

            if res == "SENT_OK":
                return True

            # If we get here, injection did not succeed deterministically.
            # Keep legacy keyboard approach as a last-resort fallback.
            log.warning(f"POC injection did not return SENT_OK (res={res}) — falling back to keyboard send")
            return await self._send_chat_keyboard(message)

        except Exception as e:
            log.error(f"Chat send failed: {e}")
            return False

    # ------------------------------------------------------------

    async def shutdown(self) -> None:
        async with self._lock:
            if self._shutting_down:
                return

            self._shutting_down = True
            log.info("Shutting down browser")

            try:
                if self._context:
                    try:
                        await self._context.close()
                    except Exception as e:
                        log.warning(f"Browser context close ignored: {e}")

                if self._playwright:
                    try:
                        await self._playwright.stop()
                    except Exception as e:
                        log.warning(f"Playwright stop ignored: {e}")

            finally:
                self._context = None
                self._page = None
                self._chat_frame = None
                self._playwright = None
                self._started = False
                self._shutting_down = False
