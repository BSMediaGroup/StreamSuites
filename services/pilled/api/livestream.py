"""Placeholder for Pilled ingest-only livestream metadata client.

Reserved for future use. The ingest-only design keeps the surface small so it
can be wired into exports/state publishers without introducing control-plane
side effects.
"""


class PilledLivestreamClient:
    def __init__(self):
        raise NotImplementedError("Pilled livestream ingest is planned, not implemented")
