import httpx
from typing import Dict, Any

from shared.logging.logger import get_logger

log = get_logger("rumble.api.livestream")

LIVESTREAM_ENDPOINT = "https://rumble.com/-livestream-api/get-data"


async def fetch_livestream_data(api_key: str) -> Dict[str, Any]:
    """
    Fetch livestream metadata for a Rumble channel.

    This endpoint is used to:
    - detect if the channel is live
    - retrieve chat room information
    - retrieve chat post endpoint paths
    """
    params = {
        "key": api_key
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(LIVESTREAM_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                log.error("Livestream API returned non-dict payload")
                return {}

            return data

        except Exception as e:
            log.error(f"Failed to fetch livestream data: {e}")
            return {}
