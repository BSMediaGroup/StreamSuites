
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class YouTubeChatMessage:
    """
    Normalized YouTube live chat message scaffold.

    The YouTube Data API exposes live chat via `liveChatMessages.list` with a
    poll-driven model. This dataclass mirrors the normalized event shape used
    by Twitch while preserving YouTube-specific metadata for future trigger
    routing and dashboard parity.
    """

    raw: Dict[str, Any]
    live_chat_id: str
    message_id: Optional[str]
    author_name: str
    text: str

    author_channel_id: Optional[str] = None
    published_at: Optional[datetime] = None
    is_owner: bool = False
    is_moderator: bool = False
    is_member: bool = False
    superchat_amount: Optional[int] = None
    superchat_currency: Optional[str] = None
    badges: list[str] = field(default_factory=list)

    def to_event(self) -> Dict[str, Any]:
        """
        Produce a minimal, trigger-ready event shape without coupling to
        downstream consumers. Future trigger registries can consume this
        output directly or map it into a shared schema.
        """
        return {
            "platform": "youtube",
            "type": "chat_message",
            "live_chat_id": self.live_chat_id,
            "user": {
                "id": self.author_channel_id,
                "name": self.author_name,
                "badges": list(self.badges),
                "is_owner": self.is_owner,
                "is_moderator": self.is_moderator,
                "is_member": self.is_member,
            },
            "message_id": self.message_id,
            "text": self.text,
            "timestamp": (
                self.published_at.astimezone(timezone.utc).isoformat()
                if self.published_at
                else None
            ),
            "superchat": {
                "amount": self.superchat_amount,
                "currency": self.superchat_currency,
            }
            if self.superchat_amount
            else None,
            "raw": self.raw,
        }
