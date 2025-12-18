"""Placeholder model for Rumble chat events.

This module defines the anticipated shape of stored chat events without
introducing any runtime dependencies. Future implementations may include
attributes such as:

    {
        "id": "event-uuid",
        "stream_id": "rumble-stream-id",
        "timestamp": "ISO-8601 string",
        "user": "display name",
        "message": "raw chat message text",
        "metadata": {}
    }

No classes or functions are defined to avoid interfering with the existing
Rumble chatbot integration.
"""
