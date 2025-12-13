import httpx
import json
import re
from typing import Dict, Any

from shared.logging.logger import get_logger

log = get_logger("rumble.api.channel_page")

CHANNEL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
    re.DOTALL
)


async def fetch_channel_livestream_state(
    channel_url: str,
    cookie: str
) -> Dict[str, Any]:
    """
    Fetch Rumble channel page HTML and extract embedded initial state.

    NOTE:
    Rumble channel pages are now Cloudflare-protected and REQUIRE
    a valid browser session cookie.
    """

    if not cookie:
        log.error("No session cookie provided — cannot fetch channel page")
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://rumble.com/",
        "Origin": "https://rumble.com",
        "Cookie": cookie,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        headers=headers
    ) as client:
        try:
            resp = await client.get(channel_url)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            log.error(f"Failed to fetch channel page: {e}")
            return {}

    match = CHANNEL_STATE_RE.search(html)
    if not match:
        log.error("Unable to locate __INITIAL_STATE__ in channel page HTML")
        return {}

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse __INITIAL_STATE__: {e}")
        return {}
