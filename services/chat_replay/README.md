# Chat Replay Scaffolding (Runtime)

This directory holds the initial runtime-side scaffolding for unified chat replay surfaces. It is intentionally static and does not implement live chat ingestion, sockets, or backend connectivity.

## Components

- **contracts/chat_message.schema.json**: Placeholder data contract describing the neutral unified chat message shape for future replay ingestion.
- **templates/chat_replay_window.html**: Pop-out style chat window modeled after modern livestream chats. Includes mock controls for pause, autoscroll, clear, and timestamp visibility.
- **templates/chat_overlay_obs.html**: Transparent browser-source-friendly overlay intended for OBS, Meld, Streamlabs, and similar tools. Limited history with fade-in message treatment.
- **static/chat.css**: Locally scoped styling shared by both templates.
- **static/chat_mock_data.js**: Static mock messages spanning multiple platforms; used by both templates until live replay engines supply data.

## Behavior and Limitations

- **No live data**: Both HTML surfaces rely on the static mock data file and do not connect to any runtime service.
- **No sockets or APIs**: Networking is not enabled; all behaviors are local-only placeholders.
- **Scaffolding only**: Controls such as pause, autoscroll, and timestamp visibility are implemented on top of mock data to illustrate UX intent without wiring to runtime events.

## Future Integration Notes

Future chat replay engines can feed these templates by replacing the mock data import with runtime-managed payloads that conform to `contracts/chat_message.schema.json`. Once a unified replay source exists, the templates can consume rendered JSON via local file reads, bundled static exports, or another runtime-safe injection path without altering the current aesthetic scaffolding.
