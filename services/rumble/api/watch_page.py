from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page and extract chat metadata
    directly from the in-page Vue / Nuxt runtime.
    """
    browser = RumbleBrowserClient.instance()
    page = await browser.get_page(watch_url)

    try:
        # Give Nuxt time to hydrate
        await page.wait_for_function(
            "window.__NUXT__ || window.$nuxt",
            timeout=15000,
        )

        state = await page.evaluate(
            """
            () => {
                if (window.__NUXT__) return window.__NUXT__;
                if (window.$nuxt && window.$nuxt.$store)
                    return window.$nuxt.$store.state;
                return null;
            }
            """
        )

        if not state:
            log.error("Nuxt state not found in page runtime")
            return {
                "is_live": False,
                "chat_room_id": None,
                "chat_post_path": None,
            }

        # Walk known Rumble structures
        video = (
            state.get("video")
            or state.get("videos", {}).get("current")
            or {}
        )

        livestream = video.get("livestream") or {}
        chat = livestream.get("chat") or video.get("chat") or {}

        room_id = chat.get("roomId")
        post_path = chat.get("postPath")

        if not room_id or not post_path:
            log.error("Chat metadata missing from Nuxt state")
            return {
                "is_live": False,
                "chat_room_id": None,
                "chat_post_path": None,
            }

        return {
            "is_live": True,
            "chat_room_id": room_id,
            "chat_post_path": post_path,
        }

    except Exception as e:
        log.error(f"Failed extracting chat state from page runtime: {e}")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
