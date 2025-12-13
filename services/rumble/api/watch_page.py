import re
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")


CHAT_ROOM_RE = re.compile(r'"chatRoomId"\s*:\s*"([^"]+)"')
CHAT_POST_RE = re.compile(r'"postPath"\s*:\s*"([^"]+)"')


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page and extract chat metadata
    by scanning embedded script payloads.

    This avoids fragile Nuxt / Vue runtime hooks and works reliably
    on Cloudflare-protected pages.
    """
    browser = RumbleBrowserClient.instance()
    page = await browser.get_page(watch_url)

    try:
        # Allow full page hydration & async script execution
        await page.wait_for_timeout(5000)

        scripts = await page.query_selector_all("script")

        for script in scripts:
            try:
                content = await script.inner_text()
            except Exception:
                continue

            if not content:
                continue

            if "chatRoomId" not in content or "postPath" not in content:
                continue

            room_match = CHAT_ROOM_RE.search(content)
            post_match = CHAT_POST_RE.search(content)

            if room_match and post_match:
                room_id = room_match.group(1)
                post_path = post_match.group(1)

                log.info(
                    f"Extracted watch-page chat metadata: room={room_id}"
                )

                return {
                    "is_live": True,
                    "chat_room_id": room_id,
                    "chat_post_path": post_path,
                }

        log.error("Unable to locate embedded chat metadata on watch page")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    except Exception as e:
        log.error(f"Failed extracting chat state from page runtime: {e}")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
