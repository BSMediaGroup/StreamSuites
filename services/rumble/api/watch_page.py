import asyncio
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page and extract chat metadata.

    Strategy:
    - Navigate with the persistent browser profile (Cloudflare-safe)
    - Wait briefly for either:
        (a) JSON/XHR responses parsed by the browser client
        (b) WebSocket URL/frame parsing (common for chat bootstraps)
    """
    browser = RumbleBrowserClient.instance()

    # Important: clear previous detection so we don’t reuse stale sessions
    browser.clear_sessions()

    try:
        await browser.navigate(watch_url)

        # Wait up to N seconds for the browser to detect a session
        timeout_s = 20
        poll_every = 0.25
        waited = 0.0

        while waited < timeout_s:
            session = browser.get_latest_session()
            if session:
                room_id = session.get("room_id")
                post_path = session.get("post_path")

                if room_id and post_path:
                    log.info(
                        f"Detected livestream chat session: room={room_id}"
                    )
                    return {
                        "is_live": True,
                        "chat_room_id": str(room_id),
                        "chat_post_path": str(post_path),
                    }

            await asyncio.sleep(poll_every)
            waited += poll_every

        log.error("No livestream chat session detected after navigation")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    except Exception as e:
        log.error(f"Watch-page chat state fetch failed: {e}")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
