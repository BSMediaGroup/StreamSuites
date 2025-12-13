import httpx
from typing import List, Dict, Any

from shared.logging.logger import get_logger

log = get_logger("rumble.api.chat")

CHAT_ENDPOINT = "https://rumble.com/service.php"


async def fetch_chat_messages(
    room_id: str,
    since: int
) -> List[Dict[str, Any]]:
    """
    Fetch chat messages newer than `since` timestamp.
    """
    params = {
        "name": "chat.get_messages",
        "room_id": room_id,
        "since": since
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(CHAT_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error(f"Chat fetch failed: {e}")
            return []

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        return []

    return messages
