from typing import Dict, Any, List

from services.triggers.base import Trigger
from shared.logging.logger import get_logger

log = get_logger("triggers.registry", runtime="streamsuites")


class TriggerRegistry:
    """
    Holds and evaluates triggers for a single creator context.

    Responsibilities:
    - Store triggers
    - Evaluate them against incoming chat events
    - Emit action descriptors (no execution)
    """

    def __init__(self, *, creator_id: str):
        self.creator_id = creator_id
        self._triggers: List[Trigger] = []

    # ------------------------------------------------------------

    def register(self, trigger: Trigger) -> None:
        """
        Register a trigger instance.
        """
        log.debug(
            f"[{self.creator_id}] Registering trigger: {trigger.trigger_id}"
        )
        self._triggers.append(trigger)

    # ------------------------------------------------------------

    def process(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all triggers against a chat event and return actions.
        """
        actions: List[Dict[str, Any]] = []

        for trigger in self._triggers:
            try:
                if not trigger.matches(event):
                    continue

                action = trigger.build_action(event)
                if action:
                    actions.append(action)

            except Exception as e:
                log.warning(
                    f"[{self.creator_id}] Trigger '{trigger.trigger_id}' "
                    f"error ignored: {e}"
                )

        return actions
