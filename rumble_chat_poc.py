"""
======================================================================
 StreamSuites Runtime — Version v0.2.0-alpha (Build 2025.01)
 Owner: Daniel Clancy
 Copyright © 2025 Brainstream Media Group
======================================================================
"""

import time
import json
from playwright.sync_api import sync_playwright

WATCH_URL = "https://rumble.com/v731j4o-testing-build-3.html"
LIVESTREAM_API_URL = "https://rumble.com/-livestream-api/get-data?key=REDACTED"
POLL_SECONDS = 2


def inject_send_message(page, text):
    return page.evaluate(
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

            // Step 4: force-enable button (React sometimes lags)
            sendBtn.disabled = false;

            // Step 5: click send
            sendBtn.click();

            return "SENT_OK";
        }
        """,
        text,
    )
    return result


def main():
    print("🔥 RUMBLE CHAT BOT — MODEL A (DOM INJECTION)")
    print("🔐 Log in manually when browser opens")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=".rumble_profile",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        page.goto("https://rumble.com/account/login")
        input("Press ENTER after login completes...")

        print(f"📺 Opening livestream → {WATCH_URL}")
        page.goto(WATCH_URL, timeout=60000)
        page.wait_for_timeout(5000)

        print("🔍 Waiting for chat input...")
        page.wait_for_selector("#chat-message-text-input", timeout=60000)
        print("✅ Chat input detected")

        seen = set()
        print("\n✅ Listening for chat...\n")

        while True:
            data = context.request.get(LIVESTREAM_API_URL).json()

            for stream in data.get("livestreams", []):
                if not stream.get("is_live"):
                    continue

                for msg in stream.get("chat", {}).get("recent_messages", []):
                    key = (msg["username"], msg["text"], msg["created_on"])
                    if key in seen:
                        continue
                    seen.add(key)

                    user = msg["username"]
                    text = msg["text"]
                    print(f"💬 {user}: {text}")

                    if text.strip().lower() == "!ping":
                        print("⚡ Trigger detected — sending pong")
                        res = inject_send_message(page, "pong")
                        print(f"📤 Inject result: {res}")

            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
