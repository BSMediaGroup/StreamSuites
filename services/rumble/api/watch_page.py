from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")


async def fetch_watch_page_chat_state(
    watch_url: str,
) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page.

    IMPORTANT:
    - This function does NOT parse HTML
    - It does NOT inspect Nuxt / Vue state
    - It simply navigates the page so that the
      browser client's network interception layer
      can detect chat bootstrap responses.

    Chat metadata is retrieved from the browser
    client AFTER navigation.
    """
    browser = RumbleBrowserClient.instance()

    # Trigger navigation (this enables response interception)
    await browser.navigate(watch_url)

    # Give network requests time to fire
    await asyncio_sleep_safe(3)

    # Ask browser client for the most recent livestream session
    session = browser.get_latest_session()

    if not session:
        log.error("No livestream chat session detected after navigation")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    return {
        "is_live": True,
        "chat_room_id": session.get("room_id"),
        "chat_post_path": session.get("post_path"),
    }


async def asyncio_sleep_safe(seconds: float):
    """
    Shielded sleep helper to avoid cancellation noise.
    """
    try:
        import asyncio
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        pass
