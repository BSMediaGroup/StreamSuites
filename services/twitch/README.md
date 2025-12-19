# Twitch services (chat foundation)

StreamSuites connects to Twitch chat via IRC-over-TLS for determinism and
operational parity with other platforms. The current scope is a foundation
layer: reliable connect/read/send with clean lifecycle boundaries. Triggers,
dashboards, and Helix usage will build on top of this scaffold.

## Components

- `api/chat.py` — Twitch IRC client (TLS, PING/PONG handling, message parsing)
- `workers/chat_worker.py` — scheduler-owned worker that wraps the IRC client
  with cancellation-safe startup/shutdown and minimal built-in trigger handling
  (`!ping -> pong` for smoke testing)
- `models/message.py` — normalized Twitch chat message with a trigger-ready
  `to_event()` helper for future central routing

No side effects occur on import; all lifecycle actions remain under scheduler
or caller control to keep parity with the Discord control-plane runtime.

## Transport

- Host: `irc.chat.twitch.tv`
- Port: `6697` (TLS)
- Auth: `PASS oauth:<token>`, `NICK <nick>`, `JOIN #<channel>`
- Capabilities: `CAP REQ :twitch.tv/tags twitch.tv/commands` for message tags
  (IDs, timestamps, user metadata)

## Environment

Required for chat:
- `TWITCH_OAUTH_TOKEN_DANIEL` — chat OAuth token (with or without the `oauth:`
  prefix; the client normalizes it)
- `TWITCH_BOT_NICK_DANIEL` — nickname used for `NICK`
- `TWITCH_CHANNEL_DANIEL` — channel to join (omit `#`)

Documented for future Helix/REST usage (not required for IRC chat):
- `TWITCH_CLIENT_ID_DANIEL`
- `TWITCH_CLIENT_SECRET_DANIEL`

## Worker lifecycle

The `TwitchChatWorker` owns a `TwitchChatClient` instance and exposes:
- `async run()` — connect, join, and stream messages while handling PING/PONG
- `async shutdown()` — cleanly PART and close the connection
- `async send_message(text)` — helper for operators or future triggers

Workers do not start automatically; the scheduler will integrate them under a
Twitch platform flag per creator to preserve runtime isolation.

## Smoke test

A repository-root script is provided for manual validation:

```bash
python twitch_chat_poc.py --channel <channel> --nick <bot-nick>
```

You can omit CLI flags when the corresponding environment variables are set.
The POC prints incoming messages and responds to `!ping` with `pong`, using the
same IRC client as the worker.
