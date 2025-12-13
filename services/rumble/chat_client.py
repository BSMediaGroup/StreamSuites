import time
import uuid
import httpx
from typing import List, Dict, Optional

from shared.logging.logger import get_logger

log = get_logger("rumble.chat_client")


class RumbleChatClient:
    """
    Direct REST client for Rumble chat.
    Auth is cookie-based ONLY.
    """

    BASE = "https://web7.rumble.com/chat/api/chat"

    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies

        self.client = httpx.Client(
            headers={
                "Origin": "https://rumble.com",
                "Referer": "https://rumble.com/",
                "User-Agent": "StreamSuitesBot/1.0",
                "Accept": "application/json",
            },
            cookies=cookies,
            timeout=10.0,
        )

    # ------------------------------------------------------------
    # SEND MESSAGE
    # ------------------------------------------------------------

    def send_message(self, channel_id: str, text: str) -> bool:
        url = f"{self.BASE}/{channel_id}/message"

        payload = {
            "data": {
                "request_id": uuid.uuid4().hex,
                "message": {"text": text},
                "rant": None,
                "channel_id": None,
            }
        }

        try:
            r = self.client.post(url, json=payload)
            if r.status_code != 200:
                log.error(f"Chat send failed [{r.status_code}]: {r.text}")
                return False
            return True
        except Exception as e:
            log.error(f"Chat send exception: {e}")
            return False

    # ------------------------------------------------------------
    # FETCH MESSAGES (POLL)
    # ------------------------------------------------------------

    def fetch_messages(
        self,
        channel_id: str,
        since_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Poll chat messages.
        """
        params = {}
        if since_id:
            params["after"] = since_id

        url = f"{self.BASE}/{channel_id}/messages"

        try:
            r = self.client.get(url, params=params)
            if r.status_code != 200:
                log.error(f"Chat fetch failed [{r.status_code}]")
                return []

            data = r.json().get("data", [])
            return data if isinstance(data, list) else []
        except Exception as e:
            log.error(f"Chat fetch exception: {e}")
            return []
