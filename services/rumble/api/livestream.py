import httpx
from typing import Dict, Any

from shared.logging.logger import get_logger

log = get_logger("rumble.api.livestream")

LIVESTREAM_ENDPOINT = "https://rumble.com/-livestream-api/get-data"


async def fetch_livestream_data(api_key: str) -> Dict[str, Any]:
    """
    Fetch livestream metadata for a Rumble channel.

    Rumble protects this endpoint with Cloudflare and expects
    browser-like headers.
    """
    params = {
        "key": api_key
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://rumble.com/",
        "Origin": "https://rumble.com"
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
