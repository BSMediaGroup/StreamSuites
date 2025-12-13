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

        # IMPORTANT:
        # - Do NOT request Brotli ("br") unless you are 100% sure brotli decode support is installed.
        # - gzip/deflate are safe defaults on Windows/Python stacks.
        self.client = httpx.Client(
            headers={
                "Origin": "https://rumble.com",
                "Referer": "https://rumble.com/",
                "User-Agent": "StreamSuitesBot/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
            cookies=cookies,
            timeout=10.0,
            follow_redirects=True,
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
                # Never dump r.text here; it may be compressed/binary depending on server behavior.
                log.error(
                    f"Chat send failed [{r.status_code}] "
                    f"(len={len(r.content) if r.content else 0}, content-type={r.headers.get('content-type')}, encoding={r.headers.get('content-encoding')})"
                )
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
        limit: int = 50,
    ) -> List[dict]:
        """
        Poll chat messages.

        - Rumble requires `limit`
        - Cursor param is `last_id`
        """
        url = f"{self.BASE}/{channel_id}/messages"

        params = {"limit": int(limit)}
        if since_id:
            params["last_id"] = str(since_id)

        try:
            r = self.client.get(url, params=params)

            if r.status_code != 200:
                log.error(
                    f"Chat fetch failed [{r.status_code}] "
                    f"(len={len(r.content) if r.content else 0}, content-type={r.headers.get('content-type')}, encoding={r.headers.get('content-encoding')})"
                )
                return []

            # If decode still fails for any reason, this will raise and we catch below.
            payload = r.json()

            data = payload.get("data", [])
            if not isinstance(data, list):
                return []

            return data

        except Exception as e:
            # Don't print bodies; just the exception.
            log.error(f"Chat fetch exception: {e}")
            return []

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
