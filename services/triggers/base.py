from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Trigger(ABC):
    """
    Base class for all chat triggers.

    Triggers are pure logic:
    - No I/O
    - No async
    - No platform awareness
    """

    def __init__(self, *, trigger_id: str):
        self.trigger_id = trigger_id

    @abstractmethod
    def matches(self, event: Dict[str, Any]) -> bool:
        """
        Return True if this trigger should fire for the given event.
        """
        raise NotImplementedError

    @abstractmethod
    def build_action(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build and return an action dict, or None if no action should occur.
        """
        raise NotImplementedError
