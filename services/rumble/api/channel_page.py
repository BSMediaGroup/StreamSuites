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

_logged_html_sample = False


async def fetch_channel_livestream_state(channel_url: str) -> Dict[str, Any]:
    browser = RumbleBrowserClient.instance()

    try:
        html = await browser.fetch_html(channel_url)
    except Exception as e:
        log.error(f"Browser fetch failed: {e}")
        return {}

    match = NUXT_STATE_RE.search(html)
    if not match:
        global _logged_html_sample
        if not _logged_html_sample:
            log.error(
                "window.__NUXT__ not found. HTML sample:\n"
                + html[:500]
            )
            _logged_html_sample = True
        return {}

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse window.__NUXT__: {e}")
        return {}
