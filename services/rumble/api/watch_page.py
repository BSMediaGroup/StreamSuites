import re
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

ROOM_RE = re.compile(r"(?:roomId|chatRoomId)=([^&]+)")
POST_RE = re.compile(r"(?:postPath|chatPostPath)=([^&]+)")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page and extract chat metadata
    by inspecting the chat iframe URL.

    This is the ONLY reliable method on modern Rumble pages.
    """
    browser = RumbleBrowserClient.instance()
    page = await browser.get_page(watch_url)

    try:
        # Wait for chat iframe to appear
        iframe = await page.wait_for_selector(
            'iframe[src*="/chat"]',
            timeout=20000
        )

        src = await iframe.get_attribute("src")
        if not src:
            raise RuntimeError("Chat iframe has no src attribute")

        room_match = ROOM_RE.search(src)
        post_match = POST_RE.search(src)

        if not room_match or not post_match:
            raise RuntimeError(f"Chat iframe src missing metadata: {src}")

        room_id = room_match.group(1)
        post_path = post_match.group(1)

        log.info(
            f"Extracted chat metadata from iframe: room={room_id}"
        )

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
