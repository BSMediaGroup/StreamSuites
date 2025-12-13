import json
import re
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

RUMBLE_STATE_PATTERNS = [
    re.compile(r"window\.__RUMBLE_STATE__\s*=\s*({.*?});", re.DOTALL),
    re.compile(r"window\.__RUMBLE_DATA__\s*=\s*({.*?});", re.DOTALL),
]


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Fetch a Rumble watch page and extract live chat metadata.
    """
    browser = RumbleBrowserClient.instance()
    html = await browser.fetch_html(watch_url)

    state = None

    # 1️⃣ Try known global state objects
    for pattern in RUMBLE_STATE_PATTERNS:
        match = pattern.search(html)
        if match:
            try:
                state = json.loads(match.group(1))
                break
            except Exception as e:
                log.error(f"Failed to parse RUMBLE state JSON: {e}")

    # 2️⃣ Fallback: script[type=application/json]
    if not state:
        for block in re.findall(
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        ):
            try:
                candidate = json.loads(block.strip())
                if isinstance(candidate, dict) and "video" in candidate:
                    state = candidate
                    break
            except Exception:
                continue

    if not state:
        log.error("Unable to locate embedded JSON state on watch page")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }

    # 3️⃣ Extract chat metadata
    try:
        video = state.get("video") or {}
        chat = video.get("chat") or {}

        room_id = chat.get("roomId")
        post_path = chat.get("postPath")

        if not room_id or not post_path:
            log.error("Chat metadata not present in watch page state")
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
        log.error(f"Failed extracting chat metadata: {e}")
        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
