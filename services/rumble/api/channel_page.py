import httpx
import json
import re
from typing import Dict, Any, Optional

from shared.logging.logger import get_logger

log = get_logger("rumble.api.channel_page")


CHANNEL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
    re.DOTALL
)


async def fetch_channel_livestream_state(
    channel_url: str,
    cookie: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch Rumble channel page HTML and extract livestream state.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html",
        "Referer": "https://rumble.com/"
    }

    if cookie:
        headers["Cookie"] = cookie

    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        try:
            resp = await client.get(channel_url)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            log.error(f"Failed to fetch channel page: {e}")
            return {}

    match = CHANNEL_STATE_RE.search(html)
    if not match:
        log.error("Unable to locate __INITIAL_STATE__ in channel page")
        return {}

    try:
        state = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse channel JSON state: {e}")
        return {}

    return state
