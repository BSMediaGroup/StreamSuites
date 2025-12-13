import json
import re
from typing import Dict, Any

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.channel_page")

CHANNEL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
    re.DOTALL
)


async def fetch_channel_livestream_state(channel_url: str) -> Dict[str, Any]:
    """
    Fetch Rumble channel page HTML via Playwright
    and extract embedded __INITIAL_STATE__ JSON.
    """
    browser = RumbleBrowserClient.instance()

    try:
        html = await browser.fetch_html(channel_url)
    except Exception as e:
        log.error(f"Browser fetch failed: {e}")
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
