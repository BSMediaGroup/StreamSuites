import uuid
import httpx

from shared.logging.logger import get_logger

log = get_logger("rumble.chat.rest")


class RumbleChatRESTClient:
    BASE = "https://web7.rumble.com/chat/api/chat"

    def __init__(self, cookies: dict):
        self.client = httpx.Client(
            cookies=cookies,
            headers={
                "Origin": "https://rumble.com",
                "Referer": "https://rumble.com/",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
            timeout=10.0,
        )

    def send(self, channel_id: str, text: str):
        url = f"{self.BASE}/{channel_id}/message"

        payload = {
            "data": {
                "request_id": uuid.uuid4().hex,
                "message": {"text": text},
                "rant": None,
                "channel_id": None,
            }
        }

        r = self.client.post(url, json=payload)

        if r.status_code != 200:
            log.error(f"Send failed [{r.status_code}]")
            return False

        return True
