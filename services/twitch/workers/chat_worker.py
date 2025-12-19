import asyncio
from typing import Optional

from services.twitch.api.chat import TwitchChatClient
from services.twitch.models.message import TwitchChatMessage
from shared.logging.logger import get_logger

log = get_logger("twitch.chat_worker", runtime="streamsuites")


class TwitchChatWorker:
    """
    Scheduler-owned Twitch chat worker (IRC over TLS).

    Responsibilities:
    - Own the TwitchChatClient lifecycle (connect, read, send, shutdown)
    - Emit normalized chat events for future trigger routing
    - Remain cancellation-safe and free of side effects on import
    """

    def __init__(
        self,
        *,
        ctx,
        oauth_token: str,
        channel: str,
        nickname: Optional[str] = None,
    ):
        if not oauth_token:
            raise RuntimeError("Twitch oauth_token is required")
        if not channel:
            raise RuntimeError("Twitch channel is required")

        self.ctx = ctx
        self.channel = channel
        self.nickname = nickname or channel
        self._client = TwitchChatClient(
            token=oauth_token,
            nickname=self.nickname,
            channel=self.channel,
        )

        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker starting")
        await self._client.connect()

        try:
            async for message in self._client.iter_messages():
                await self._handle_message(message)

                if self._stop_event.is_set():
                    break

        except asyncio.CancelledError:
            log.debug(f"[{self.ctx.creator_id}] Twitch chat worker cancelled")
            raise
        except Exception as e:
            log.error(f"[{self.ctx.creator_id}] Twitch chat worker error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        await self._client.close()
        log.info(f"[{self.ctx.creator_id}] Twitch chat worker stopped")

    # ------------------------------------------------------------------ #

    async def send_message(self, text: str) -> None:
        """
        Public helper for future trigger dispatchers or operators.
        """
        await self._client.send_message(text)

    # ------------------------------------------------------------------ #

    async def _handle_message(self, message: TwitchChatMessage) -> None:
        """
        Internal routing hook for chat messages. Keeps the logic minimal to
        avoid overlapping with future trigger registries.
        """
        event = message.to_event()

        log.info(
            f"[{self.ctx.creator_id}] [#{message.channel}] "
            f"{message.username}: {message.text}"
        )

        # Placeholder for central trigger routing
        # TODO: integrate with trigger registry when available
        await self._handle_builtin_triggers(event, message)

    async def _handle_builtin_triggers(
        self,
        event: dict,
        message: TwitchChatMessage,
    ) -> None:
        """
        Minimal safety trigger for smoke testing.
        """
        text = (event.get("text") or "").strip().lower()
        if text == "!ping":
            await self.send_message("pong")
