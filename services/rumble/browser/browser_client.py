import asyncio
from pathlib import Path
from typing import Optional
import uuid

from playwright.async_api import async_playwright, BrowserContext, Page, Frame
from shared.logging.logger import get_logger

log = get_logger("rumble.browser")


class RumbleBrowserClient:
    """
    MODEL A — DOM INJECTION BROWSER CLIENT (POC-LOCKED)

    HARD LAWS:
    - Persistent profile (cookies ONLY)
    - ONE authoritative page
    - CHAT SUBMIT MUST USE IFRAME-SCOPED DOM EVENTS + BUTTON CLICKS (no Enter)
    """

    _instance: Optional["RumbleBrowserClient"] = None

    def __init__(self):
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._chat_frame: Optional[Frame] = None
        self._chat_binding_name: Optional[str] = None

        self._profile_dir = Path(".browser") / "rumble"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        self._started = False
        self._shutting_down = False

    # ------------------------------------------------------------

    @property
    def started(self) -> bool:
        return self._started

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
    # AUTH COOKIE EXPORT (FOR NON-DOM CLIENTS)
    # ------------------------------------------------------------

    async def export_cookies(self, for_domains: Optional[list[str]] = None) -> list:
        """
        Export cookies from the persistent browser context so downstream HTTP
        clients (e.g., SSE) can reuse the authenticated session. Optional
        domain filtering keeps the jar tight to rumble hosts.
        """
        if not self._context:
            raise RuntimeError("Browser context not ready")

        cookies = await self._context.cookies()

        if for_domains:
            normalized = [d.lstrip(".") for d in for_domains]

            def _matches(domain: str) -> bool:
                dom = domain.lstrip(".")
                return any(dom == nd or dom.endswith(f".{nd}") for nd in normalized)

            cookies = [c for c in cookies if _matches(c.get("domain", ""))]

        return cookies

    # ------------------------------------------------------------
    # 🔥 AUTHORITATIVE CHAT SEND — IFRAME-SCOPED DOM INJECTION (NO ENTER)
    # ------------------------------------------------------------

    async def _send_chat_injection(self, message: str) -> str:
        """
        Deterministic chat send that stays inside the chat iframe and clicks the
        real send button (no Enter keypresses). React-friendly events ensure the
        input updates reliably before the click.
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

                input.focus();

                input.value = "";
                input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward", data: "" }));

                input.value = msg;
                input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: msg }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }));

                if (sendBtn.disabled) {
                    sendBtn.removeAttribute("disabled");
                }

                sendBtn.click();

                return "SENT_OK";
            }
            """,
            message,
        )

    # ------------------------------------------------------------
    # PAYMENT / MODAL GUARD
    # ------------------------------------------------------------

    async def _dismiss_payment_modals(self) -> None:
        if not self._page:
            return

        selectors = [
            "div.modal.show button.btn-close",
            "div.modal.show button.close",
            "div.modal.show [data-bs-dismiss='modal']",
            "div.modal.show .modal-footer button",
            "div.modal.show .modal-header button",
        ]

        for sel in selectors:
            try:
                modal_btn = await self._page.query_selector(sel)
                if modal_btn:
                    log.info(f"Closing blocking modal via selector={sel}")
                    await modal_btn.click()
                    await asyncio.sleep(0.2)
                    return
            except Exception:
                continue

    # ------------------------------------------------------------

    async def send_chat_dom(self, message: str) -> bool:
        if not self._chat_frame:
            raise RuntimeError("Chat frame not initialized")

        input_selector = "#chat-message-text-input"
        send_selector = "button.chat--send"

        try:
            await self._dismiss_payment_modals()

            log.info(
                f"Sending via DOM (iframe scoped) input={input_selector} send_button={send_selector}"
            )

            res = await self._send_chat_injection(message)

            if res == "SENT_OK":
                # Confirm send by checking the input clears or a DOM mutation fires
                try:
                    cleared = await self._chat_frame.wait_for_selector(
                        f"{input_selector}[value='']",
                        timeout=1500,
                        state="attached",
                    )
                    if cleared:
                        log.info("Chat send confirmed via input clear")
                        return True
                except Exception:
                    pass

                # Final guard: read the input value directly
                try:
                    value = await self._chat_frame.eval_on_selector(
                        input_selector, "el => el && el.value"
                    )
                    if value in (None, ""):
                        log.info("Chat send confirmed via input value empty")
                        return True
                except Exception:
                    pass

                log.warning("Chat send not confirmed via DOM; treating as failure")
                return False

            log.error(
                f"DOM injection did not return SENT_OK (res={res}) — send aborted (no Enter fallback)"
            )
            return False

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

    # ------------------------------------------------------------
    # CHAT DOM OBSERVER (for ingest fallback + send confirmation)
    # ------------------------------------------------------------

    async def start_chat_observer(self, queue: asyncio.Queue) -> Optional[str]:
        """
        Inject a MutationObserver into the chat iframe that reports new chat
        message nodes back to Python through a unique Playwright binding.

        Returns the binding name used, or None if the observer could not be
        attached. Consumers should listen to the binding events separately.
        """

        if not self._page or not self._chat_frame:
            log.warning("Cannot attach chat observer — chat frame not ready")
            return None

        if self._chat_binding_name:
            return self._chat_binding_name

        binding_name = f"rumbleChatObserver_{uuid.uuid4().hex}"

        try:
            await self._page.expose_binding(
                binding_name,
                lambda source, payload: queue.put_nowait(payload),
            )
        except Exception as e:
            log.error(f"Failed to expose chat binding: {e}")
            return None

        script = r"""
            (bindingName) => {
                const send = (payload) => {
                    if (!globalThis[bindingName]) return;
                    try {
                        globalThis[bindingName](payload);
                    } catch (err) {
                        console.error('Chat observer dispatch failed', err);
                    }
                };

                const rootCandidates = [
                    document.querySelector('[data-test-selector="chat-messages"]'),
                    document.querySelector('[data-testid="chat-messages"]'),
                    document.querySelector('#chat-messages'),
                    document.querySelector('.chat-messages'),
                    document.body
                ].filter(Boolean);

                const target = rootCandidates[0];
                if (!target) {
                    send({ type: 'observer_error', reason: 'no_target' });
                    return 'NO_TARGET';
                }

                const normalize = (node) => {
                    const usernameEl = node.querySelector('[data-username], .chat--username, .user-name, .username');
                    const textEl = node.querySelector('[data-message-text], .chat--message, .message-text, .content');
                    const timeEl = node.querySelector('time, [data-timestamp], .timestamp');

                    const username = usernameEl ? (usernameEl.textContent || '').trim() : '';
                    const text = textEl ? (textEl.textContent || '').trim() : '';
                    const ts = timeEl ? ((timeEl.getAttribute('datetime') || timeEl.textContent || '').trim()) : '';

                    if (!username || !text) return null;
                    return { username, text, timestamp: ts || null };
                };

                const seen = new WeakSet();

                const emitExisting = () => {
                    const candidates = target.querySelectorAll('[data-chat-message], li, div');
                    candidates.forEach((node) => {
                        if (seen.has(node)) return;
                        const normalized = normalize(node);
                        if (normalized) {
                            seen.add(node);
                            send({ type: 'chat', payload: normalized });
                        }
                    });
                };

                emitExisting();

                const observer = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                        m.addedNodes.forEach((node) => {
                            if (!(node instanceof HTMLElement)) return;
                            if (seen.has(node)) return;
                            const normalized = normalize(node);
                            if (normalized) {
                                seen.add(node);
                                send({ type: 'chat', payload: normalized });
                            }
                            node.querySelectorAll && node.querySelectorAll('[data-chat-message], li, div').forEach((child) => {
                                if (seen.has(child)) return;
                                const childNorm = normalize(child);
                                if (childNorm) {
                                    seen.add(child);
                                    send({ type: 'chat', payload: childNorm });
                                }
                            });
                        });
                    }
                });

                observer.observe(target, { childList: true, subtree: true });
                send({ type: 'observer_ready' });
                return 'BOUND';
            }
        """

        try:
            result = await self._chat_frame.evaluate(script, binding_name)
            if result == "BOUND":
                self._chat_binding_name = binding_name
                log.info("Chat MutationObserver attached (binding=%s)", binding_name)
                return binding_name
            log.warning(f"Chat observer failed to bind: {result}")
        except Exception as e:
            log.error(f"Failed to attach chat observer: {e}")

        return None

    async def stop_chat_observer(self) -> None:
        self._chat_binding_name = None
