import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Optional, Tuple

from services.twitch.models.message import TwitchChatMessage
from shared.logging.logger import get_logger

log = get_logger("twitch.chat", runtime="streamsuites")


class TwitchChatClient:
    """
    Minimal Twitch IRC-over-TLS client for chat I/O.

    - No event loop creation on import.
    - Connection lifecycle is owned by callers (workers or POC scripts).
    - Focuses on determinism and verbose logging for operator visibility.
    """

    HOST = "irc.chat.twitch.tv"
    PORT = 6697

    def __init__(
        self,
        token: str,
        nickname: str,
        channel: str,
        *,
        request_tags: bool = True,
    ):
        self.token = self._normalize_token(token)
        self.nickname = nickname
        self.channel = self._normalize_channel(channel)
        self.request_tags = request_tags

        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

        self._connected = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def connect(self) -> None:
        """
        Establish TLS IRC connection and join the configured channel.
        """
        if self._connected:
            log.debug("TwitchChatClient already connected")
            return

        log.info(
            f"Connecting to Twitch IRC ({self.HOST}:{self.PORT}) "
            f"as nick={self.nickname} channel=#{self.channel}"
        )
        self.reader, self.writer = await asyncio.open_connection(
            self.HOST, self.PORT, ssl=True
        )

        await self._send_raw(f"PASS {self.token}")
        await self._send_raw(f"NICK {self.nickname}")

        if self.request_tags:
            await self._send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands")

        await self._send_raw(f"JOIN #{self.channel}")
        self._connected = True
        log.info(f"Joined Twitch channel #{self.channel}")

    async def close(self) -> None:
        if not self.writer:
            return

        log.info("Closing Twitch IRC connection")
        try:
            await self._send_raw("PART #" + self.channel)
        except Exception:
            pass

        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            log.debug(f"Error during Twitch IRC close ignored: {e}")
        finally:
            self.reader = None
            self.writer = None
            self._connected = False

    # ------------------------------------------------------------------ #
    # Messaging
    # ------------------------------------------------------------------ #

    async def send_message(self, text: str) -> None:
        if not text.strip():
            return

        await self._send_raw(f"PRIVMSG #{self.channel} :{text}")
        log.info(f"[#{self.channel}] Sent chat message ({len(text)} chars)")

    async def iter_messages(self) -> AsyncGenerator[TwitchChatMessage, None]:
        """
        Read chat lines and yield parsed TwitchChatMessage instances.
        """
        if not self.reader:
            raise RuntimeError("iter_messages called before connect()")

        while True:
            line = await self.reader.readline()

            if line == b"":
                # Connection closed by remote
                log.warning("Twitch IRC connection closed by remote")
                break

            decoded = line.decode("utf-8", errors="ignore").strip()
            if not decoded:
                continue

            if decoded.startswith("PING"):
                await self._handle_ping(decoded)
                continue

            msg = self._parse_privmsg(decoded)
            if msg:
                yield msg

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _send_raw(self, data: str) -> None:
        if not self.writer:
            raise RuntimeError("IRC writer is not initialized")

        payload = (data + "\r\n").encode("utf-8")
        self.writer.write(payload)
        await self.writer.drain()

    async def _handle_ping(self, raw: str) -> None:
        # Twitch IRC sends: PING :tmi.twitch.tv
        payload = raw.split(" ", 1)[-1]
        await self._send_raw(f"PONG {payload}")
        log.debug("Responded to Twitch PING")

    def _parse_privmsg(self, raw: str) -> Optional[TwitchChatMessage]:
        """
        Parse a PRIVMSG line into a TwitchChatMessage. Other commands are
        ignored to keep the loop deterministic.
        """
        tags, remainder = self._split_tags(raw)
        prefix, command, params = self._split_prefix_and_command(remainder)

        if command != "PRIVMSG" or len(params) < 2:
            return None

        channel = params[0].lstrip("#")
        text = params[1]

        username = self._parse_username(prefix)
        if not username:
            username = tags.get("display-name") or "unknown"

        timestamp = self._parse_timestamp(tags.get("tmi-sent-ts"))

        message = TwitchChatMessage(
            raw=raw,
            username=username,
            channel=channel,
            text=text,
            message_id=tags.get("id"),
            user_id=tags.get("user-id"),
            room_id=tags.get("room-id"),
            badges=self._parse_badges(tags.get("badges")),
            timestamp=timestamp,
        )

        log.debug(
            f"[#{channel}] {username}: {text} "
            f"(id={message.message_id}, ts={message.timestamp})"
        )

        return message

    @staticmethod
    def _split_tags(raw: str) -> Tuple[Dict[str, str], str]:
        if raw.startswith("@"):
            tags_part, remainder = raw.split(" ", 1)
            tags = {}
            for pair in tags_part[1:].split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    tags[k] = v
            return tags, remainder

        return {}, raw

    @staticmethod
    def _split_prefix_and_command(raw: str) -> Tuple[str, str, Tuple[str, ...]]:
        prefix = ""
        rest = raw
        if raw.startswith(":"):
            if " " in raw:
                prefix, rest = raw[1:].split(" ", 1)
            else:
                prefix = raw[1:]
                rest = ""

        if " :" in rest:
            middle, trailing = rest.split(" :", 1)
            parts = middle.split()
            if not parts:
                return prefix, "", tuple()
            command = parts[0]
            params = tuple(parts[1:] + [trailing])
        else:
            parts = rest.split()
            if not parts:
                return prefix, "", tuple()
            command = parts[0]
            params = tuple(parts[1:])

        return prefix, command, params

    @staticmethod
    def _parse_username(prefix: str) -> str:
        # Prefix example: nickname!nickname@nickname.tmi.twitch.tv
        if "!" in prefix:
            return prefix.split("!", 1)[0]
        return prefix or ""

    @staticmethod
    def _parse_timestamp(raw_ts: Optional[str]) -> Optional[datetime]:
        if not raw_ts:
            return None
        try:
            millis = int(raw_ts)
            return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _parse_badges(raw_badges: Optional[str]) -> list[str]:
        if not raw_badges:
            return []
        return [badge for badge in raw_badges.split(",") if badge]

    @staticmethod
    def _normalize_token(token: str) -> str:
        token = token.strip()
        if not token.startswith("oauth:"):
            return f"oauth:{token}"
        return token

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        return channel.lstrip("#").strip()
