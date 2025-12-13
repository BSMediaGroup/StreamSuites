from typing import Callable

from shared.logging.logger import get_logger

log = get_logger("rumble.chat.ws")


class RumbleChatWSListener:
    def __init__(self, channel_id: str, on_message: Callable[[dict], None]):
        self.channel_id = str(channel_id)
        self.on_message = on_message

    def handle_ws_event(self, data: dict):
        """
        Called for every WS frame.
        Filters to chat messages only.
        """
        if not isinstance(data, dict):
            return

        # Rumble chat messages typically look like:
        # { "type": "message", "data": { ... } }
        if data.get("type") != "message":
            return

        msg = data.get("data")
        if not isinstance(msg, dict):
            return

        # Ensure it's from the correct channel
        if str(msg.get("channel_id")) != self.channel_id:
            return

        self.on_message(msg)
