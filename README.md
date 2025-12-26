# StreamSuites

StreamSuites is a modular, multi-platform livestream automation system. It is
the single canonical runtime source for orchestrating streaming data-plane
workers and control-plane automation across platforms such as Discord,
YouTube, Twitch, Twitter/X, and Rumble. Tallies are now tracked as a
first-class runtime concept alongside polls and clips, with schema-only
scaffolding in place for future dashboard/public visibility.

## Version & Release Authority

- **Current version**: v0.2.0-alpha (Build 2025.01)
- **Development stage**: Late Alpha — features are present but still undergoing hardening, observability work, and lifecycle tightening before beta stabilization.
- **Versioning policy**: Semantic Versioning with pre-release tags (e.g., `-alpha`, `-beta`) to signal stability and readiness. Pre-release identifiers reflect runtime maturity and do not guarantee API permanence.
- **Authoritative runtime**: This repository is the authoritative runtime source of truth for StreamSuites. Dashboard and external consumers are strictly read-only and must not mutate runtime-managed state.
- **Licensing notice**: Proprietary / All Rights Reserved. Redistribution or reuse outside authorized channels is not permitted.
- **Production readiness**: Not production ready. Expect breaking changes, schema adjustments, and operational refinements during the late alpha cycle.

The project is built with a strong emphasis on:
- deterministic behavior
- clean lifecycle management
- platform-specific correctness
- future extensibility without architectural rewrites

The first implemented and validated platform was **Rumble**; Rumble support is
currently paused (see status below) but all code remains intact for
re-enablement.

## Project Status

- **Stabilization milestone**: quota enforcement and quota snapshot export are
  complete. Runtimes are focused on hardening, observability, and boundary
  cleanup before expanding feature surface area.
- **Dashboard compatibility**: dashboard-generated `creators.json` and
  `platforms.json` are ingested via `core/config_loader.py` with schema
  validation, and the streaming runtime publishes `shared/state/runtime_snapshot.json`
  for dashboard telemetry.
- **Public export readiness**: read-only snapshot builders for public clips and
  polls galleries are available under `shared/public_exports/` with a static
  export root at `exports/public/` for future publishing. Tallies are prepared
  as a distinct schema for future read-only snapshots without sharing poll
  logic or storage.

## Runtime data, signals, and exports (Data & Signals readiness)

The runtime is the **authoritative data source**, **signal processor**, and
**export generator** for the Data & Signals dashboard. It owns raw events and
controls how they are shaped for consumption while keeping dashboard access
strictly read-only. Snapshot files under `runtime/exports/`, `runtime/signals/`,
and `runtime/admin/` are deterministic, timestamped JSON documents that can be
mirrored into the dashboard repository or any static host. The dashboard never
mutates runtime state; it only reads the published snapshots.

- **Authoritative data source**: runtime workers own the canonical state for
  clips, polls, tallies, scoreboards, creators, and quotas.
- **Signal processor**: normalized chat, poll, tally, and score events are
  captured for dashboard inspection without enabling writes or action
  execution.
- **Export generator**: deterministic JSON snapshots are produced for public
  galleries, dashboard-only operations, and internal integration surfaces.

### Data & Signals integration contract

- Dashboard consumption is **read-only**. Snapshots are written by the runtime
  and optionally mirrored into the dashboard `docs/data/` root or another
  hosting path.
- Snapshots include a `meta` block with timestamps, source identifiers, and
  visibility tags (`public`, `dashboard-only`, `internal-only`) so the
  dashboard can filter without relying on file placement alone.
- Future sync paths (e.g., file-based or HTTP) must continue to respect the
  read-only boundary; no live mutation from dashboard surfaces is permitted.

### Export visibility reference

| File | Location | Visibility | Notes |
| --- | --- | --- | --- |
| `clips.json` | `runtime/exports/` | Public | Published clips snapshot, safe for public galleries. |
| `polls.json` | `runtime/exports/` | Public | Poll questions + aggregated votes, no voter identifiers. |
| `tallies.json` | `runtime/exports/` | Public | Aggregate tally counts only. |
| `scoreboards.json` | `runtime/exports/` | Public | Ranked scoreboard entries with scores. |
| `meta.json` | `runtime/exports/` | Public | Manifest describing the export surface. |
| `chat_events.json` | `runtime/signals/` | Dashboard-only | Normalized chat events for inspection. |
| `poll_votes.json` | `runtime/signals/` | Dashboard-only | Individual poll vote events without personal data. |
| `tally_events.json` | `runtime/signals/` | Dashboard-only | Increment events for tallies. |
| `score_events.json` | `runtime/signals/` | Dashboard-only | Score adjustments feeding scoreboards. |
| `creators.json` | `runtime/admin/` | Dashboard-only | Creator registry snapshot. |
| `chat_triggers.json` | `runtime/admin/` | Dashboard-only | Trigger definitions for reference only. |
| `jobs.json` | `runtime/admin/` | Dashboard-only | Job queue visibility (read-only). |
| `rate_limits.json` | `runtime/admin/` | Dashboard-only | Rate limit policies visible to operators. |
| `integrations.json` | `runtime/admin/` | Internal-only | Integration endpoints and statuses. |
| `permissions.json` | `runtime/admin/` | Internal-only | Placeholder for future principal/role mapping. |

### Runtime changelog ownership

- Runtime authors maintain the canonical changelog structure in `changelog/changelog.runtime.json`; this file defines the authoritative JSON shape expected by the dashboard.
- Exports for distribution live under `runtime/exports/changelog.runtime.json` and must be produced manually or by CI tooling — the runtime does **not** emit changelog files during execution.
- The dashboard repository merges and renders runtime and dashboard changelog surfaces client-side; no manual merging is required once the export is updated.
- Public changelog views remain a merged surface while the runtime stays authoritative over runtime-originated entries.
- The runtime remains the authoritative source for changelog data, while the dashboard stays read-only and presentational when rendering the merged public surface.

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

## Clipping module (runtime)

The runtime owns a deterministic, SQLite-backed clipping module that runs in
the background with bounded concurrency. Core properties:

- **Purpose**: accept clip requests, encode with FFmpeg, upload to a default
  Rumble destination, and export state for the dashboard.
- **Lifecycle states** (persisted and exported): `queued`, `encoding`,
  `encoded`, `uploading`, `published`, `failed`.
- **Encoding model**: background worker (`services/clips/worker.py`) with
  default concurrency of `2` (configurable via `shared/config/system.json`).
  Output naming is deterministic: `clips/output/{clip_id}.mp4` with
  `clip_id` as a 6-character alphanumeric token.
- **SQLite usage**: tables `clips`, `clip_jobs`, and `clip_state_history` live
  in `data/streamsuites.db` and are created on boot if missing. State changes
  are recorded atomically for observability.
- **FFmpeg dependency**: the runtime defaults to
  `X:\\ffmpeg\\bin\\ffmpeg.exe` (Windows-first) and falls back to `ffmpeg` on
  PATH if that path does not exist locally. No auto-installation is attempted.
- **Export surface**: snapshots are written to `shared/state/clips.json` every
  30 seconds **and** immediately on state changes, mirroring to the dashboard
  publish root when configured.
- **Destination resolution**: the default upload target is read dynamically
  from `shared/config/system.json` (`clips.default_destination.channel_url`)
  and currently points to `https://rumble.com/c/StreamSuites`. Architecture
  permits future per-creator overrides without changing the runtime contract.

### Trigger System (design-locked)

- Platform-agnostic trigger registry lives under `services/triggers/`.
- Triggers evaluate **normalized chat events** and emit **action descriptors**
  (pure data). Execution of any action is intentionally **deferred** to a
  later phase.
- Trigger types are design-locked, even when partially scaffolded:
  - Command triggers (e.g., `!clip`, `!ping`)
  - Regex-based triggers
  - Keyword-based triggers
  - Cooldowns across user / creator / global scopes
- The registry is creator-scoped and platform-neutral so chat workers can
  publish uniformly shaped events without embedding business logic.

### Quota architecture (runtime only)

- **QuotaTracker** (enforcement only): in-process daily quota enforcement with
  buffer + hard-cap handling; tracks usage per creator/platform without writing
  files or persisting state.
- **QuotaRegistry** (authoritative, in-memory): global registry that owns all
  QuotaTrackers for the running process; exposes snapshots for aggregation.
- **Snapshot merge**: runtime cadence aggregates all registered trackers via
  `shared/runtime/quotas_snapshot.py` and writes a single
  `shared/state/quotas.json` document through `DashboardStatePublisher`
  (optionally mirrored to the dashboard publish root).

### Runtime vs dashboard boundary

- **Runtime ownership**: control-plane + streaming runtimes own authoritative
  state generation (jobs, triggers, quotas) under `shared/state/` and publish
  via `DashboardStatePublisher`. Quota enforcement and cadence loops live only
  in the runtime.
- **Dashboard consumption**: the dashboard is read-only; it reads published
  state snapshots (jobs, runtime status, quotas) and never mutates runtime
  state. Overrides are handled through query parameters and static hosting
  roots without changing runtime behavior.

## Dashboard state publishing

The Discord control-plane runtime emits live snapshots for the dashboard under
`shared/state/discord/runtime.json` (runtime + heartbeat state) and
`shared/state/jobs.json` (job queue/timestamps). The streaming runtime exports
`shared/state/runtime_snapshot.json` via `core/state_exporter.py`, reflecting
platform enablement, telemetry toggles, creator registry status, and recent
heartbeats. Snapshots are written
atomically and can optionally be mirrored into the dashboard hosting root by
setting `DASHBOARD_STATE_PUBLISH_ROOT` (or `STREAMSUITES_STATE_PUBLISH_ROOT`)
to the Pages/bucket checkout path. If unset, the runtime will auto-detect a
local `../StreamSuites-Dashboard` checkout (docs root) when present. A helper
script is available for cron or CI runs when the runtime is not active:

```bash
python scripts/publish_state.py --target ../StreamSuites-Dashboard/docs
```

### Dashboard lookup order

The dashboard now resolves state roots in the following order:

1) `stateRoot` query parameter (persisted to `localStorage` as
   `streamsuites.stateRootOverride` for future loads)
2) The published `./shared/state/` directory within the dashboard hosting root
3) Fallback to the runtime repository's raw URL:
   `https://raw.githubusercontent.com/BSMediaGroup/StreamSuites/main/shared/state/`

To serve snapshots from another host or bucket, open the dashboard with
`?stateRoot=<your-url>/` (ensure the trailing slash) and the override will be
remembered. The fallback works only when this repository publishes current
snapshots under `shared/state/discord/runtime.json` (and optional
`shared/state/jobs.json`) so the raw GitHub URL always contains valid data.

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

### Chat worker responsibilities (current state)

- Twitch and YouTube chat workers connect to their respective platforms,
  normalize incoming messages, and pass normalized events into the
  `TriggerRegistry` for evaluation.
- Workers log emitted trigger actions for observability. **They do not execute
  actions**, dispatch jobs, or persist cooldowns.
- Business logic is intentionally deferred; workers remain limited to transport
  ownership, normalization, and trigger evaluation.

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

### Scheduler role (clarified)

- Owns lifecycle of platform workers per creator, based on platform flags in
  `shared/config/creators.json`.
- Starts chat workers; **does not evaluate triggers** and **does not execute
  trigger actions**.
- Coordinates shutdown and resource cleanup across runtimes.

## Current Platform Status

- Discord: **ACTIVE** — control-plane only, separate runtime, not part of the
  chat-trigger pipeline.
- YouTube: **SCAFFOLDED** — polling-based chat worker is trigger-ready; API
  calls and livestream discovery are deferred pending credentials/quota.
- Twitch: **FOUNDATION** — IRC-based chat worker implemented, architecture is
  complete and trigger-ready; temporarily untestable due to external account
  issues.
- Twitter/X: **PLANNED** — control-plane tasks exist; runtime worker scaffold is
  not yet implemented.
- Rumble: **PAUSED** — browser/DOM-based approach retained and documented; execution is paused
  due to upstream API protection. Architecture remains intact for reactivation.

### YouTube chat (scaffold)

- Transport: **polling** via `liveChatMessages.list` (no push/webhook support)
- Poll cadence: honor `pollingIntervalMillis`; default scaffold assumes ~2–3s
  while API hints are wired
- Rate limits: `liveChatMessages.list` costs 5 units/request; current quota is
  200,000 units/day with ~50,000 reserved for overhead/other tasks, so keep
  intervals above 2s to avoid churn
- Latency: expect a few seconds between message send and API availability;
  downstream triggers must tolerate slight delays and deduplicate by message ID
- Lifecycle: scheduler-owned workers will resolve `liveChatId` and poll chat;
  implementation is deferred until the scaffold is validated
- Normalization: chat messages are normalized into platform-agnostic events,
  evaluated by the `TriggerRegistry`, and any emitted trigger actions are
  logged only (execution deferred)

Environment:
- `YOUTUBE_API_KEY_DANIEL` — Data API key used for livestream discovery and
  chat polling

## Rumble integration (paused)

All Rumble chat workers, models, and browser helpers remain in the repository.
Execution is paused solely due to upstream API protection and DDoS mitigation.
The architecture and code paths are intentionally preserved to allow rapid
re-enablement once official API access or platform whitelisting is available.

## Repository Structure

```text
StreamSuites/
├── changelog/
│   ├── README.md              # Canonical runtime changelog expectations (manual/CI copy to dashboard)
│   └── changelog.runtime.json # Authoritative runtime changelog JSON format (structure only)
├── runtime/
│   └── exports/
│       ├── changelog.json         # Legacy runtime changelog shape
│       ├── changelog.runtime.json # Authoritative runtime changelog entries (client-side merged by dashboard)
│       ├── clips.json             # Clips export snapshot (public)
│       ├── meta.json              # Export manifest
│       ├── polls.json             # Polls export snapshot (public)
│       ├── scoreboards.json       # Scoreboards export snapshot (public)
│       └── tallies.json           # Tallies export snapshot (public)
├── core/
│   ├── README.md             # Core runtime boundaries and status
│   ├── app.py                # Streaming runtime entrypoint & lifecycle
│   ├── config_loader.py      # Dashboard-compatible config ingestion + validation
│   ├── context.py            # Per-creator runtime context
│   ├── discord_app.py        # Discord control-plane runtime entrypoint
│   ├── jobs.py               # Job registry and dispatch
│   ├── ratelimits.py         # Shared ratelimit helpers
│   ├── registry.py           # Creator loading and validation
│   ├── scheduler.py          # Task orchestration and shutdown control
│   ├── state_exporter.py     # Runtime snapshot export (platform + creators)
│   ├── shutdown.py           # Coordinated shutdown helpers
│   ├── signals.py            # Signal handling
│   └── tallies/              # Tally schema-only runtime concept (no execution)
│       ├── README.md         # Scope and future readiness for tallies
│       ├── __init__.py       # Export surface for tally dataclasses
│       └── models.py         # Tally, category, option dataclasses + serialization
│
├── services/
│   ├── clips/
│   │   ├── __init__.py
│   │   ├── encoder.py         # FFmpeg wiring + deterministic outputs
│   │   ├── exporter.py        # Clip state snapshot publisher
│   │   ├── manager.py         # Clip runtime facade (queue + worker + export)
│   │   ├── models.py          # Clip identifiers, title formatting, states
│   │   ├── storage.py         # SQLite-backed clip persistence
│   │   └── worker.py          # Background worker + concurrency guardrails
│   ├── discord/
│   │   ├── README.md         # Discord control-plane runtime architecture
│   │   ├── announcements.py  # Control-plane notifications
│   │   ├── client.py         # DiscordClient connection + command surface
│   │   ├── commands/
│   │   │   ├── README.md     # Command layering rules
│   │   │   ├── __init__.py
│   │   │   ├── admin.py      # Admin handlers (pure logic)
│   │   │   ├── admin_commands.py
│   │   │   ├── creators.py   # Creator-scoped handler scaffold
│   │   │   ├── public.py     # Public handler scaffold
│   │   │   └── services.py   # Service-level handler scaffold
│   │   ├── heartbeat.py      # Heartbeat loop for liveness
│   │   ├── logging.py        # Logging adapters
│   │   ├── permissions.py    # Admin gating via Discord-native flags
│   │   ├── runtime/
│   │   │   ├── README.md     # Discord lifecycle ownership & supervision
│   │   │   ├── __init__.py   # Discord runtime scaffolding
│   │   │   ├── lifecycle.py  # Lifecycle hooks for Discord control-plane
│   │   │   └── supervisor.py # Supervisor for control-plane runtime
│   │   ├── status.py         # Shared-state status persistence
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
│   │   ├── chat_client.py
│   │   ├── models/
│   │   │   ├── chat_event.py
│   │   │   ├── message.py
│   │   │   └── stream.py
│   │   └── workers/
│   │       ├── chat_worker.py      # Chat read/write logic
│   │       └── livestream_worker.py
│   ├── triggers/                   # Platform-agnostic trigger registry
│   │   ├── __init__.py
│   │   ├── base.py                 # Trigger interface (matches + build_action)
│   │   ├── README.md               # Trigger pipeline concepts and score event notes
│   │   └── registry.py             # Creator-scoped trigger evaluation (emit actions)
│   ├── twitch/
│   │   ├── README.md
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
│       ├── README.md
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
│   │   ├── monetization.json
│   │   ├── posting_rules.json
│   │   ├── ratelimits.json
│   │   ├── services.json
│   │   ├── services.py
│   │   ├── system.json
│   │   ├── system.py
│   │   └── tiers.json
│   ├── logging/
│   │   ├── levels.py
│   │   └── logger.py
│   ├── public_exports/       # Read-only builders for public gallery exports
│   │   ├── __init__.py
│   │   ├── clips.py
│   │   ├── polls.py
│   │   └── publisher.py
│   ├── ratelimiter/
│   │   └── governor.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── quotas.py
│   │   ├── quotas_snapshot.py
│   │   └── scoreboards_snapshot.py
│   ├── scoreboards/
│   │   ├── README.md
│   │   ├── placeholders.py
│   │   ├── registry.py
│   │   ├── schema.json
│   │   └── snapshot.py
│   ├── state/
│   │   ├── chat_logs/
│   │   │   ├── .gitkeep
│   │   │   └── rumble/
│   │   │       └── .gitkeep
│   │   ├── creators/
│   │   │   └── daniel.json
│   │   ├── discord/
│   │   │   ├── README.md
│   │   │   └── guilds/
│   │   │       └── .gitkeep
│   │   ├── jobs.json
│   │   ├── scoreboards/
│   │   │   ├── .gitkeep
│   │   │   ├── creators/
│   │   │   │   └── .gitkeep
│   │   │   └── snapshots/
│   │   │       └── .gitkeep
│   │   └── system.json
│   ├── storage/
│   │   ├── chat_events/        # Placeholder for chat event persistence
│   │   │   ├── __init__.py
│   │   │   ├── index.py
│   │   │   ├── reader.py
│   │   │   ├── schema.json
│   │   │   └── writer.py
│   │   ├── file_lock.py
│   │   ├── paths.py
│   │   ├── state/
│   │   │   └── discord/
│   │   │       └── discord_status.json
│   │   ├── scoreboards/
│   │   │   ├── README.md
│   │   │   ├── exporter.py
│   │   │   └── importer.py
│   │   ├── state_publisher.py
│   │   └── state_store.py
│   └── utils/
│       ├── files.py
│       ├── hashing.py
│       ├── retry.py
│       └── time.py
├── schemas/
│   ├── creators.schema.json
│   ├── platforms.schema.json
│   └── ...                   # Additional dashboard schemas (chat, jobs, quotas, etc.)
│
├── clips/
│   └── output/                # Deterministic clip outputs (clip_id).mp4
│       └── .gitkeep
├── exports/
│   └── public/                # Static snapshot root for public gallery exports
│       └── .gitkeep
│
├── runtime/
│   ├── exports/               # Deterministic public-facing snapshot files
│   │   ├── clips.json
│   │   ├── polls.json
│   │   ├── tallies.json
│   │   ├── scoreboards.json
│   │   └── meta.json
│   ├── signals/               # Dashboard-only normalized events
│   │   ├── chat_events.json
│   │   ├── poll_votes.json
│   │   ├── tally_events.json
│   │   └── score_events.json
│   ├── admin/                 # Dashboard/internal operational snapshots
│   │   ├── creators.json
│   │   ├── chat_triggers.json
│   │   ├── jobs.json
│   │   ├── rate_limits.json
│   │   ├── integrations.json
│   │   └── permissions.json
│   └── version.py             # Application/runtime version information
│
├── data/
│   └── streamsuites.db        # SQLite runtime store (auto-created)
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
│   ├── publish_state.py
│   └── validate_config.py
│
├── tests/
│   └── __init__.py
│
├── rumble_chat_poc.py        # Rumble chat validation script
├── twitch_chat_poc.py        # Twitch chat IRC smoke test
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

## Twitch chat foundation (IRC-over-TLS)

Twitch connectivity uses the native IRC-over-TLS transport to keep behavior
deterministic and scheduler-friendly. Foundational pieces live under:

- `services/twitch/api/chat.py` — Twitch IRC client (connect/read/send, PING/PONG)
- `services/twitch/workers/chat_worker.py` — worker lifecycle wrapper for
  scheduler ownership (no side effects on import); normalizes chat events and
  routes them into the platform-agnostic `TriggerRegistry`, logging emitted
  trigger actions without executing them.
- `services/twitch/models/message.py` — normalized chat message + trigger-ready
  event shape

### Environment

Twitch tokens live in `.env`:

- `TWITCH_OAUTH_TOKEN_DANIEL` (required for IRC chat)
- `TWITCH_BOT_NICK_DANIEL` (chat nickname; defaults to channel name if omitted)
- `TWITCH_CHANNEL_DANIEL` (channel to join without the `#` prefix)
- `TWITCH_CLIENT_ID_DANIEL` / `TWITCH_CLIENT_SECRET_DANIEL` (documented for
  future Helix usage; not required for IRC chat)

### Smoke test (standalone)

A minimal Twitch chat validation script lives at the repo root:

```bash
python twitch_chat_poc.py --channel <channel> --nick <bot-nick>
# or rely on env vars: TWITCH_OAUTH_TOKEN_DANIEL, TWITCH_CHANNEL_DANIEL, TWITCH_BOT_NICK_DANIEL
```

The script connects to `irc.chat.twitch.tv:6697`, prints incoming messages, and
responds to `!ping` with `pong`. Scheduler integration will attach the same
worker/client lifecycle when Twitch is enabled for a creator. Discord and other
runtimes remain unchanged.

---

## Roadmap

### Implemented
- Quota enforcement (per-creator/platform, daily, buffer + hard cap)
- Quota snapshot export (runtime cadence → `shared/state/quotas.json`)
- Discord control-plane runtime scaffolding + dashboard state publish
- Twitch and YouTube chat trigger scaffolds (evaluation-only)
- Rumble chat workers (paused, preserved)

### Short-term
- Harden quota registry wiring across platform workers
- Expand dashboard quota surface for observability only
- Tighten shutdown ordering across runtimes
- Validate YouTube/Twitch trigger scaffolds with live credentials

### Medium-term
- Config-driven trigger definitions and cooldown persistence
- Dashboard tooling for creator config introspection (read-only first)
- Additional platform workers (Twitter/X control-plane parity)
- Scheduler telemetry + alert surfaces

### Long-term
- Trigger action execution + job dispatch
- Operator tooling (desktop control, runtime start/stop)
- Historical chat logging + replay (opt-in)
- Dashboard trigger editing and live controls

---

## Notes
This repository intentionally prioritizes correctness and clarity over
rapid feature accumulation. All new functionality is expected to respect
the existing lifecycle and architectural boundaries.

---
