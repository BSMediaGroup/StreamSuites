import json
import re
from typing import Dict, Any

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.channel_page")

NUXT_STATE_RE = re.compile(
    r"window\.__NUXT__\s*=\s*({.*?});",
    re.DOTALL
)


async def fetch_channel_livestream_state(channel_url: str) -> Dict[str, Any]:
    """
    Fetch Rumble channel page HTML via Playwright
    and extract embedded Nuxt state.
    """
    browser = RumbleBrowserClient.instance()

    try:
        html = await browser.fetch_html(channel_url)
    except Exception as e:
        log.error(f"Browser fetch failed: {e}")
        return {}

    match = NUXT_STATE_RE.search(html)
    if not match:
        log.error("Unable to locate window.__NUXT__ in channel page HTML")
        return {}

    try:
        state = json.loads(match.group(1))
        return state
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse window.__NUXT__: {e}")
        return {}
