# StreamSuites

StreamSuites is a modular, multi-platform livestream automation system. It is
the single canonical runtime source for orchestrating streaming data-plane
workers and control-plane automation across platforms such as Discord,
YouTube, Twitch, Twitter/X, and Rumble.

The project is built with a strong emphasis on:
- deterministic behavior
- clean lifecycle management
- platform-specific correctness
- future extensibility without architectural rewrites

The first implemented and validated platform was **Rumble**; Rumble support is
currently paused (see status below) but all code remains intact for
re-enablement.

---

## Architecture Overview

StreamSuites is evolving into a multi-runtime architecture while remaining a
single repository. Runtimes are explicitly isolated by responsibility and
started by a shared scheduler:

- Streaming runtimes (per platform) live under `core/app.py` and platform
  services. They own ingestion, publishing, and data-plane orchestration.
- The Discord control-plane runtime lives under `core/discord_app.py`
  (standalone entrypoint) and is optionally started by the scheduler. It offers
  admin/status commands and notification routing without embedding ingestion.
- Shared configuration and state live under `shared/`, with platform-neutral
  helpers under `services/`.

Both entrypoints are independent runtime processes. The scheduler coordinates
lifecycles while keeping control-plane behavior separate from streaming logic.

## Dashboard state publishing

The Discord control-plane runtime emits live snapshots for the dashboard under
`shared/state/discord/runtime.json` (runtime + heartbeat state) and
`shared/state/jobs.json` (job queue/timestamps). Snapshots are written
atomically and can optionally be mirrored into the dashboard hosting root by
setting `DASHBOARD_STATE_PUBLISH_ROOT` (or `STREAMSUITES_STATE_PUBLISH_ROOT`)
to the Pages/bucket checkout path. If unset, the runtime will auto-detect a
local `../StreamSuites-Dashboard` checkout (docs root) when present. A helper
script is available for cron or CI runs when the runtime is not active:

```bash
python scripts/publish_state.py --target ../StreamSuites-Dashboard/docs
```

### Discord control-plane runtime (overview)

- Purpose: process-scoped control-plane runtime for operational commands,
  status surfaces, and notifications. It is not a streaming bot and never
  launches ingestion workers.
- Modes:
  - Standalone: `python -m core.discord_app`.
  - Integrated: started by `core.scheduler` when Discord is enabled in config.
- Responsibilities: DiscordClient ownership, DiscordSupervisor lifecycle,
  heartbeat loop, and shared-state status persistence.
- Separation: does not create its own event loop in integrated mode, does not
  own scheduler logic, and runs alongside streaming runtimes without coupling
  shutdown.
- Configuration: feature-gated per creator via `shared/config/creators.json`
  platform flags and runtime settings under `shared/config/`.

### High-level flow

1. Application bootstraps environment and creator contexts
2. Scheduler launches per-creator runtimes
3. Platform workers manage platform-specific logic
4. Shared browser and job systems are centrally controlled
5. Clean shutdown propagates through all active tasks

### ASCII architecture diagram

```
              +-------------------+
              |   shared/ config  |
              +---------+---------+
                        |
                +-------+-------+
                |   services/   |
                +-------+-------+
                        |
        +---------------+---------------+
        |                               |
 +------+-------+                 +-----+------+
 | core/app.py  |                 | core/      |
 | (streaming   |                 | discord_   |
 |  runtime)    |                 | app.py     |
 +------+-------+                 | (Discord   |
        |                         |  control   |
        |                         |  plane)    |
        |                         +-----+------+
  +-----+------+                       |
  | streaming  |                       | (no ingestion workers)
  | workers    |                       |
  +------------+                 +-----+------+
                                Discord bots &
                                control flows
```

---

## Streaming runtime orchestration

The streaming runtime (`core/app.py`) continues to operate as a long-running
asynchronous process orchestrated by a central scheduler and composed of
platform-specific workers.

High-level streaming flow:

1. Application bootstraps environment and creator contexts
2. Scheduler launches per-creator streaming runtimes
3. Platform workers manage platform-specific ingestion and publishing logic
4. Shared browser and job systems are centrally controlled
5. Clean shutdown propagates through all active tasks

---

## Control-plane and ownership boundaries

- `core/app.py` remains the streaming runtime authority for event loops,
  scheduler control, and shutdown.
- The scheduler may start the Discord runtime but does so in isolation so it
  can be independently restarted without interrupting streaming workers.
- Discord control-plane behavior belongs under `services/discord/` and its
  runtime scaffolding; no Discord logic should live inside `core/app.py`.
- Dashboard integration is planned (GitHub Pages first, Wix Studio later) and
  will share interfaces with the Discord control-plane for parity.

## Current Platform Status

- Discord: **ACTIVE** (optional control-plane runtime and services scaffolded)
- YouTube: **ACTIVE**
- Twitch: **ACTIVE**
- Twitter/X: **ACTIVE**
- Rumble: **PAUSED** — upstream API protection/DDoS mitigation limits access;
  all code is retained for reactivation when official access/whitelisting is
  restored. No functionality has been removed. Rumble chat bot is temporarily
  paused due to upstream API changes. All code is retained and unmodified
  pending official support.

## Rumble integration (paused)

All Rumble chat workers, models, and browser helpers remain in the repository.
Execution is paused solely due to upstream API protection and DDoS mitigation.
The architecture and code paths are intentionally preserved to allow rapid
re-enablement once official API access or platform whitelisting is available.

## Repository Structure

```text
StreamSuites/
├── core/
│   ├── README.md             # Core runtime boundaries and status
│   ├── app.py                # Streaming runtime entrypoint & lifecycle
│   ├── context.py            # Per-creator runtime context
│   ├── jobs.py               # Job registry and dispatch
│   ├── registry.py           # Creator loading and validation
│   ├── discord_app.py        # Discord control-plane runtime entrypoint
│   ├── scheduler.py          # Task orchestration and shutdown control
│   ├── shutdown.py           # Coordinated shutdown helpers
│   └── signals.py            # Signal handling
│
├── services/
│   ├── discord/
│   │   ├── README.md         # Discord control-plane runtime architecture
│   │   ├── client.py         # DiscordClient connection + command surface
│   │   ├── permissions.py    # Admin gating via Discord-native flags
│   │   ├── runtime/
│   │   │   ├── README.md     # Discord lifecycle ownership & supervision
│   │   │   ├── __init__.py   # Discord runtime scaffolding
│   │   │   ├── lifecycle.py  # Lifecycle hooks for Discord control-plane
│   │   │   └── supervisor.py # Supervisor for control-plane runtime
│   │   ├── status.py         # Shared-state status persistence
│   │   ├── heartbeat.py      # Heartbeat loop for liveness
│   │   ├── logging.py        # Logging adapters
│   │   ├── announcements.py  # Control-plane notifications
│   │   ├── commands/
│   │   │   ├── README.md     # Command layering rules
│   │   │   ├── admin.py      # Admin handlers (pure logic)
│   │   │   ├── creators.py   # Creator-scoped handler scaffold
│   │   │   ├── public.py     # Public handler scaffold
│   │   │   └── services.py   # Service-level handler scaffold
│   │   └── tasks/
│   │       ├── README.md     # Control-plane task constraints
│   │       ├── pilled_live.py
│   │       ├── rumble_live.py
│   │       ├── twitch_live.py
│   │       ├── twitter_posting.py
│   │       └── youtube_live.py
│   ├── pilled/
│   │   └── api/
│   │       ├── chat.py
│   │       └── livestream.py
│   ├── rumble/
│   │   ├── api/
│   │   │   ├── channel_page.py
│   │   │   ├── chat.py
│   │   │   └── chat_post.py
│   │   ├── browser/
│   │   │   └── browser_client.py   # Persistent Playwright browser control
│   │   ├── chat/
│   │   │   ├── rest_client.py
│   │   │   └── ws_listener.py
│   │   ├── models/
│   │   │   ├── chat_event.py
│   │   │   ├── message.py
│   │   │   └── stream.py
│   │   └── workers/
│   │       ├── chat_worker.py      # Chat read/write logic
│   │       └── livestream_worker.py
│   ├── twitch/
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   └── livestream.py
│   │   ├── models/
│   │   │   └── message.py
│   │   └── workers/
│   │       └── chat_worker.py
│   ├── twitter/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   └── posting.py
│   │   └── workers/
│   │       └── posting_worker.py
│   └── youtube/
│       ├── api/
│       │   ├── chat.py
│       │   └── livestream.py
│       ├── models/
│       │   ├── message.py
│       │   └── stream.py
│       └── workers/
│           ├── chat_worker.py
│           └── livestream_worker.py
│
├── shared/
│   ├── config/               # Static configuration (JSON)
│   │   ├── chat_behaviour.json
│   │   ├── clip_rules.json
│   │   ├── creators.json
│   │   ├── logging.json
│   │   ├── posting_rules.json
│   │   ├── ratelimits.json
│   │   ├── services.json
│   │   ├── system.json
│   │   └── tiers.json
│   ├── logging/
│   │   ├── levels.py
│   │   └── logger.py
│   ├── ratelimiter/
│   │   └── governor.py
│   ├── storage/
│   │   ├── file_lock.py
│   │   ├── paths.py
│   │   ├── state_store.py
│   │   └── chat_events/        # Placeholder for chat event persistence
│   │       ├── __init__.py
│   │       ├── index.py
│   │       ├── reader.py
│   │       ├── schema.json
│   │       └── writer.py
│   ├── utils/
│   │   ├── files.py
│   │   ├── hashing.py
│   │   ├── retry.py
│   │   └── time.py
│   └── state/
│       ├── creators/
│       │   └── daniel.json
│       ├── discord/
│       │   ├── README.md
│       │   └── guilds/
│       │       └── .gitkeep
│       ├── jobs.json
│       ├── system.json
│       └── chat_logs/          # Runtime-generated chat logs (gitignored)
│           └── rumble/
│
├── media/
│   ├── capture/
│   │   ├── rumble.py
│   │   ├── twitch.py
│   │   └── youtube.py
│   ├── jobs/
│   │   ├── base.py
│   │   ├── clip_job.py
│   │   └── upload_job.py
│   ├── processing/
│   │   ├── metadata.py
│   │   ├── transcode.py
│   │   └── trim.py
│   └── storage/
│       ├── buffer.py
│       ├── cleanup.py
│       └── clips.py
│
├── scripts/
│   ├── bootstrap.py
│   └── validate_config.py
│
├── logs/                    # Runtime logs (gitignored)
├── .browser/                # Playwright persistent profile (gitignored)
├── tests/                    # Test harness placeholder
│   └── __init__.py
│
├── rumble_chat_poc.py        # Rumble chat validation script
├── test_rumble_api.py        # Rumble API probe
├── requirements.txt
├── .env.example
├── .gitignore
├── rumble_poc/               # Persistent browser profile for Rumble PoC
└── README.md
```
--- 

## Design Principles
- **Authoritative data sources**
Platform APIs are used where available; browser automation is used
only when required.

- **Single responsibility per component**
Browsers do browser things. Workers do platform things. The scheduler
controls lifecycle.

- **No hidden background state**
All long-running tasks are tracked and cancellable.

- **Windows-first compatibility**
Signal handling, shutdown, and event loops are designed to behave
correctly on Windows.

- **Configuration over code**
Behavior is being progressively externalized into JSON-based config.

---

## Chat Event Logging & Replay (Planned / Optional)

StreamSuites may optionally capture chat events while platform bots are active
to support historical replay and downstream analysis. Any future logging will
be append-only, non-blocking, and explicitly optional so that failures never
affect live chat operations. Logged data is intended for external consumers
such as the StreamSuites dashboard, browser extensions, or moderation tools.

Planned scaffolding includes:
- A storage placeholder at `shared/storage/chat_events/` for future writers,
  readers, and indexing utilities
- A runtime state root at `shared/state/chat_logs/` (with a Rumble namespace
  at `shared/state/chat_logs/rumble/`) reserved for generated data and kept
  gitignored
- A `services/rumble/models/chat_event.py` placeholder for describing Rumble
  chat event shapes without impacting current integrations

No logging logic is implemented yet.

---

## Roadmap (High-Level)
### Phase 1 — Core Stabilization (current)
- Rumble chat read/write
- Clean lifecycle
- Rate limiting
- Startup sync control

### Phase 2 — Configuration Externalization
- Chat behavior configuration (JSON)
- Rate limit configuration
- Trigger definitions

### Phase 3 — Dashboard Tooling
- HTML-based dashboard (GitHub Pages compatible)
- Creator configuration UI
- Job visibility and status
- Schema-driven validation

### Phase 4 — Multi-Platform Expansion
- Discord integration
- YouTube integration
- Twitch integration
- Shared user identity where feasible

### Phase 5 — Operator Tooling
- Windows desktop control application
- Runtime start/stop
- Configuration management
- Log inspection

### Optional Add-On Features
- Persistent livestream chat logging
- Historical chat replay tooling
- External consumers (dashboard, browser extensions)

---

## Notes
This repository intentionally prioritizes correctness and clarity over
rapid feature accumulation. All new functionality is expected to respect
the existing lifecycle and architectural boundaries.

---
