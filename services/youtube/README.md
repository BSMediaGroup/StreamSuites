# YouTube services (chat scaffold)

StreamSuites is adding a YouTube live chat foundation that mirrors the Twitch
architecture while respecting YouTube's polling-only model. This directory
contains scaffolded modules to keep lifecycle ownership under the scheduler
without implementing network calls yet.

## Components

- `api/chat.py` — YouTube chat client scaffold for `liveChatMessages.list`
  polling, interval handling, and message normalization.
- `api/livestream.py` — Lookup scaffold for resolving the active `liveChatId`
  (via `liveBroadcasts.list`) before chat polling starts.
- `workers/chat_worker.py` — Scheduler-owned worker that will poll chat and
  emit normalized events once implemented; currently logs placeholder status.
- `workers/livestream_worker.py` — Resolves active livestream metadata to feed
  chat workers; implementation is deferred but the contract is defined.
- `models/message.py` — Normalized YouTube chat message with a `to_event()`
  helper aligned to Twitch event shapes.
- `models/stream.py` — Lightweight livestream metadata holder with `is_live()`
  convenience.

No side effects occur on import. All lifecycle actions remain under scheduler
or caller control to mirror Twitch and keep control-plane boundaries clear.

## Chat ingestion model

- Transport: **polling only** via `liveChatMessages.list` (no push/webhook).
- Poll cadence: honor `pollingIntervalMillis` from responses; default scaffold
  uses 2.5s until the API hints are wired.
- Pagination: maintain `nextPageToken` between polls; drop/refresh tokens on
  HTTP 4xx to avoid stale cursors.
- Latency: API responses may lag a few seconds; downstream triggers should
  tolerate slight delays and deduplicate by `message.id`.
- Rate limits: YouTube Data API applies a 10,000 units/day quota by default;
  `liveChatMessages.list` costs 5 units/request. Keep poll intervals above 2s
  and batch retrieval with `maxResults` hints once implemented.

## Worker lifecycle

- `YouTubeLivestreamWorker` will resolve the `liveChatId` for a creator/channel
  and hand it to chat workers. It is cancellable and side-effect free.
- `YouTubeChatWorker` will poll chat using `YouTubeChatClient`, normalize
  messages, and forward them to the trigger registry (future work). For now it
  exits after logging that the implementation is pending.

## Environment

Required for chat scaffold:
- `YOUTUBE_API_KEY_DANIEL` — YouTube Data API key for live chat polling and
  livestream discovery.

Future expansions may introduce OAuth and per-creator credentials; for now the
API key is the only documented requirement.
