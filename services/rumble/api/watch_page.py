import re
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

ROOM_RE = re.compile(r"(?:roomId|chatRoomId)=([^&]+)")
POST_RE = re.compile(r"(?:postPath|chatPostPath)=([^&]+)")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Extract Rumble livestream chat metadata by piercing the <rumble-chat>
    shadow DOM and reading the embedded iframe src.

    This is the ONLY reliable method.
    """
    browser = RumbleBrowserClient.instance()
    page = await browser.get_page(watch_url)

    try:
        # Wait for the custom element itself
        await page.wait_for_selector("rumble-chat", timeout=20000)

        result = await page.evaluate(
            """
            () => {
              const host = document.querySelector('rumble-chat');
              if (!host || !host.shadowRoot) return null;

              const iframe = host.shadowRoot.querySelector('iframe');
              if (!iframe) return null;

              return iframe.src || null;
            }
            """
        )

        if not result:
            raise RuntimeError("Chat iframe not found inside rumble-chat shadowRoot")

        room_match = ROOM_RE.search(result)
        post_match = POST_RE.search(result)

        if not room_match or not post_match:
            raise RuntimeError(f"Chat iframe src missing metadata: {result}")

        room_id = room_match.group(1)
        post_path = post_match.group(1)

        log.info(f"Extracted chat metadata via shadow DOM: room={room_id}")

        return {
            "is_live": True,
            "chat_room_id": room_id,
            "chat_post_path": post_path,
        }

    except Exception as e:
        log.error(f"No livestream chat session detected: {e}")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
