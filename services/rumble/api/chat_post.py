import httpx
from shared.logging.logger import get_logger

log = get_logger("rumble.api.chat_post")


async def post_chat_message(
    cookie: str,
    post_path: str,
    message: str
) -> bool:
    """
    Post a message to Rumble live chat using a session cookie.
    """
    url = f"https://rumble.com{post_path}"

    headers = {
        "Cookie": cookie,
        "Origin": "https://rumble.com",
        "Referer": "https://rumble.com/",
        "Accept": "*/*",
        "Content-Length": "0"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            log.debug("Chat message posted successfully")
            return True
        except Exception as e:
            log.error(f"Failed to post chat message: {e}")
            return False
