"""
======================================================================
 StreamSuites™ Runtime — Version v0.2.2-alpha (Build 2025.03)
Owner: Daniel Clancy
 Copyright © 2026 Brainstream Media Group
======================================================================
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from services.twitch.api.chat import TwitchChatClient
from shared.logging.logger import get_logger

log = get_logger("twitch.poc", runtime="streamsuites")


def _env(key: str) -> str:
    return os.getenv(key, "").strip()


async def _run(args) -> None:
    load_dotenv()

    token = args.token or _env("TWITCH_OAUTH_TOKEN_DANIEL")
    channel = args.channel or _env("TWITCH_CHANNEL_DANIEL")
    nickname = args.nick or _env("TWITCH_BOT_NICK_DANIEL") or channel

    if not token:
        raise RuntimeError(
            "Missing Twitch token. Provide --token or set TWITCH_OAUTH_TOKEN_DANIEL"
        )
    if not channel:
        raise RuntimeError(
            "Missing Twitch channel. Provide --channel or set TWITCH_CHANNEL_DANIEL"
        )
    if not nickname:
        raise RuntimeError(
            "Missing Twitch nickname. Provide --nick or set TWITCH_BOT_NICK_DANIEL"
        )

    client = TwitchChatClient(
        token=token,
        nickname=nickname,
        channel=channel,
    )

    async def _print_loop():
        async for msg in client.iter_messages():
            print(f"💬 {msg.username} → {msg.text}")
            if msg.text.strip().lower() == "!ping":
                await client.send_message("pong")

    await client.connect()
    log.info("Twitch chat POC connected — listening for messages")

    try:
        await _print_loop()
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received — shutting down POC")
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StreamSuites Twitch chat smoke test (IRC over TLS)"
    )
    parser.add_argument("--channel", help="Twitch channel to join (without #)")
    parser.add_argument("--nick", help="Bot nickname (defaults to channel name)")
    parser.add_argument("--token", help="OAuth token (with or without oauth: prefix)")

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
