from typing import Dict, Any, Optional

from services.triggers.base import Trigger


class NonEmptyChatValidationTrigger(Trigger):
    """Trivial validation trigger proving end-to-end flow.

    Fires whenever a chat event contains non-empty text. The emitted action is a
    deterministic descriptor that downstream executors can log without mutating
    platform state.
    """

    def __init__(self):
        super().__init__(trigger_id="validation.non_empty_chat")

    def matches(self, event: Dict[str, Any]) -> bool:
        return bool((event.get("text") or "").strip())

    def build_action(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return {
            "action": "validation_passed",
            "trigger_id": self.trigger_id,
            "platform": event.get("platform"),
            "creator_id": event.get("creator_id"),
            "summary": "Non-empty chat message observed",
            "text": event.get("text"),
        }
