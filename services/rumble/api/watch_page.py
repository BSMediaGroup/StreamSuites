import asyncio
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    browser = RumbleBrowserClient.instance()
    browser.clear_sessions()

    await browser.get_page(watch_url)

    deadline = asyncio.get_event_loop().time() + 25.0

    while asyncio.get_event_loop().time() < deadline:
        sess = browser.get_latest_session()
        if sess:
            log.info(
                f"Chat session acquired via WebSocket: room={sess['room_id']} ({sess['kind']})"
            )
            return {
                "is_live": True,
                "chat_room_id": sess["room_id"],
                "chat_post_path": sess["post_path"],
            }
        await asyncio.sleep(0.5)

    log.error("No livestream chat session detected via WebSocket")
    return {
        "is_live": False,
        "chat_room_id": None,
        "chat_post_path": None,
    }
