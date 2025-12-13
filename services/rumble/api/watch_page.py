import json
import re
from typing import Optional, Dict

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

# Rumble embeds state as JSON.parse("....")
JSON_PARSE_RE = re.compile(
    r'JSON\.parse\("(.+?)"\)',
    re.DOTALL
)


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Fetch a Rumble watch page and extract chat metadata.
    """
    browser = RumbleBrowserClient.instance()
    html = await browser.fetch_html(watch_url)

    match = JSON_PARSE_RE.search(html)
    if not match:
        log.error("Unable to locate embedded JSON state on watch page")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    try:
        # Unescape the JSON string
        raw = match.group(1)
        raw = raw.encode("utf-8").decode("unicode_escape")
        state = json.loads(raw)
    except Exception as e:
        log.error(f"Failed to parse watch page JSON: {e}")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    chat = (
        state
        .get("video", {})
        .get("chat", {})
    )

    room_id = chat.get("roomId")
    post_path = chat.get("postPath")

    if not room_id or not post_path:
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
