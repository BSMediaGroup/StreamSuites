from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TwitchChatMessage:
    """
    Normalized Twitch chat message (IRC over TLS).

    This shape is intentionally platform-focused while remaining compatible
    with the future central trigger engine. The `to_event` helper emits a
    trigger-friendly structure without introducing a registry dependency yet.
    """

    raw: str
    username: str
    channel: str
    text: str

    message_id: Optional[str] = None
    user_id: Optional[str] = None
    room_id: Optional[str] = None
    badges: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None

    def to_event(self) -> Dict[str, Any]:
        """
        Produce a minimal, trigger-ready event shape without coupling to
        downstream consumers. Future trigger registries can consume this
        output directly or map it into a shared schema.
        """
        return {
            "platform": "twitch",
            "type": "chat_message",
            "channel": self.channel,
            "user": {
                "id": self.user_id,
                "name": self.username,
                "badges": list(self.badges),
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
