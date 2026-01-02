"""Placeholder for Pilled ingest-only chat client.

This file intentionally contains no executable logic. It documents the planned
interface for a future ingest-only Pilled client that would normalize incoming
chat into the shared trigger/event schema without supporting outbound sends.
"""


class PilledChatClient:
    def __init__(self):
        raise NotImplementedError("Pilled chat ingest is planned, not implemented")
