import httpx
import os
from typing import Dict, Any

from shared.logging.logger import get_logger

log = get_logger("rumble.api.livestream")

LIVESTREAM_ENDPOINT = "https://rumble.com/-livestream-api/get-data"


async def fetch_livestream_data(api_key: str, creator_id: str) -> Dict[str, Any]:
    """
    Fetch livestream metadata for a Rumble channel.

    NOTE:
    - This endpoint now requires BOTH:
        - livestream API key
        - valid Cloudflare + session cookies
    """
    params = {
        "key": api_key
    }

    cookie = os.getenv(
        f"RUMBLE_BOT_SESSION_COOKIE_{creator_id.upper()}"
    )

    if not cookie:
        log.error("Missing RUMBLE_BOT_SESSION_COOKIE for livestream fetch")
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://rumble.com/",
        "Origin": "https://rumble.com",
        "Cookie": cookie
    }

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            resp = await client.get(LIVESTREAM_ENDPOINT, params=params)
            resp.raise_for_status()

            data = resp.json()
            if not isinstance(data, dict):
                log.error("Livestream API returned non-dict payload")
                return {}

            return data

        except httpx.HTTPStatusError as e:
            log.error(
                f"Failed to fetch livestream data: "
                f"{e.response.status_code} {e.response.reason_phrase}"
            )
            return {}

        except Exception as e:
            log.error(f"Failed to fetch livestream data: {e}")
            return {}
