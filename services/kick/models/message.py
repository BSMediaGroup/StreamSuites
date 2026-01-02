from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class KickChatMessage:
    raw: Dict[str, Any]
    username: str
    channel: str
    text: str

    user_id: Optional[str] = None
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def to_event(self) -> Dict[str, Any]:
        return {
            "platform": "kick",
            "type": "chat_message",
            "channel": self.channel,
            "user": {
                "id": self.user_id,
                "name": self.username,
            },
            "message_id": self.message_id,
            "text": self.text,
            "timestamp": (
                self.timestamp.astimezone(timezone.utc).isoformat()
                if self.timestamp
                else None
            ),
            "raw": self.raw,
        }
