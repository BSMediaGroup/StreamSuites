<div style="background-color:#fffae6; border:1px solid #e0a800; padding:12px;">
<strong>STATUS: ALPHA PREVIEW — StreamSuites Runtime Engine</strong><br/>
The StreamSuites Runtime is the authoritative execution layer. Runtime exports are the single source of truth. 
Dashboards and overlays consume exported artifacts only and remain read-only until live runtime plumbing is explicitly enabled.
</div>

# StreamSuites™

## Runtime Positioning

- **Project status:** Late Alpha (`0.2.3-alpha`). The runtime is stable enough for export generation and local inspection, but active runtime ↔ UI coupling is still under construction.
- **Runtime authority:** This repository is the authoritative home of the StreamSuites Runtime Engine. All execution, state, telemetry, exports, and lifecycle control originate here.
- **Dashboard separation:** All dashboard UIs live in separate repositories and consume runtime-exported artifacts only. No dashboard initiates runtime execution or mutates runtime state.
- **What is live:** Export generation, schemas, runtime metadata, versioning, and historical scaffolding. Existing exports remain authoritative for inspection.
- **What is not live yet:** Live chat ingestion, socket wiring, OBS overlay feeds, browser extension hydration, and real-time UI synchronization remain preview-only and are not wired to the runtime.
- **Ownership boundary:** The runtime guards data-plane correctness and lifecycle control. Dashboards, overlays, and extensions must remain read-only and avoid mutation paths.

StreamSuites is a modular, multi-platform livestream automation system.  
It is the **single canonical runtime source** for orchestrating streaming data-plane workers and control-plane automation across platforms such as Discord, YouTube, Twitch, Twitter/X, and Rumble.

Tallies are tracked as a **first-class runtime concept** alongside polls and clips. Schema-level scaffolding is in place for future dashboard and public visibility, but no live mutation paths are exposed.

## Version & Release Authority

- **Current version:** `0.2.3-alpha`
- **Development stage:** Late Alpha — features are present but still undergoing hardening, observability improvements, and lifecycle tightening prior to beta stabilization.
- **Versioning model:** Semantic Versioning with pre-release identifiers (`-alpha`, `-beta`) to signal maturity. Pre-release versions do not guarantee API or schema stability.
- **Build identifiers:** Build values stamp regenerated artifacts, exports, documentation, and binaries for traceability. Build changes may occur without feature changes.
- **Authoritative source:** This repository defines the authoritative version and build metadata for StreamSuites.
- **Runtime/UI separation:** Dashboards (including the web dashboard) do not execute runtime logic and are not coupled to runtime lifecycles.
- **Export-driven surfaces:** Runtime publishes state exclusively via file-based exports (JSON snapshots, manifests, and static HTML replay templates).
- **Licensing:** Proprietary. Redistribution or reuse outside authorized channels is not permitted.
- **Production readiness:** Not production-ready. Expect breaking changes, schema refinements, and operational adjustments throughout the late-alpha phase.

## Architecture Overview

- The StreamSuites Runtime repository is the authoritative source for:
  - runtime execution
  - platform workers
  - state and telemetry
  - export generation
  - changelogs and version metadata
- All control-plane and data-plane sources originate here.
- Dashboards, overlays, and extensions are **downstream consumers only**.

## Discord Integration Overview

- The Discord bot supports **per-guild** configuration.
- All Discord configuration is scoped by `guild_id`.
- The runtime is the **authoritative** executor of Discord behavior.

Discord logging and notifications are configured per guild:
- **Logging** is **disabled by default** and must be explicitly enabled with a
  designated logging channel.
- **Notification channels** are optional and can be set for general events or
  per-platform clip notifications.

## Per-Guild Discord Configuration

- Each Discord guild has isolated configuration keyed by `guild_id`.
- Logging is **off by default** and must be explicitly enabled with a target
  channel.
- Notification channels are optional and platform-specific.

Supported notification categories:
- General
- Rumble clips
- YouTube clips
- Kick clips
- Pilled clips
- Twitch clips

## WinForms Desktop Admin (Authoritative)

- **Location:** `desktop-admin/`
- Lives in **this repository**.
- Runs locally on the same machine as the runtime.
- Local, privileged, and **authoritative**.
- Does **not** use Discord OAuth.
- Can configure **all connected guilds** without restriction.
- Retains **direct filesystem access** to runtime exports and snapshots.
- Reads runtime state directly from disk without additional services.
- Can launch and terminate runtime processes as part of a privileged local control plane.
- Manages local paths and configuration to align exports with operator expectations.
- Intended for operators with direct runtime access; this authority model is by design,
  not a missing security feature.

## Web Dashboard Relationship

- The web dashboard is **not** in this repository.
- It consumes runtime-exported state only.
- It is gated by Discord OAuth (documented elsewhere).
- It has **no process control**, **no filesystem authority**, and **no write paths**.
- Runtime remains the **authoritative** executor for all behavior.

## Versioning Policy

- **VERSION** (e.g. `0.2.3-alpha`)
  - Represents semantic capability level.
  - Changes indicate meaningful feature, behavior, or contract evolution.
- **BUILD** (e.g. `YYYY.MM.DD+NNN`)
  - Represents generated artifacts and CI traceability.
  - May change without functional differences.

Version changes imply project evolution.  
Build changes imply refreshed artifacts.

## Version Consumption Matrix

- **Runtime:** Source of truth for version and build metadata.
- **WinForms Desktop Admin:** Reads and displays runtime version/build directly.
- **Web Dashboard:** Reads version/build from exported JSON and never defines its own values.

## Path & State Flow

- `runtime/exports/runtime_snapshot.json` is the authoritative runtime snapshot.
- The WinForms Desktop Admin reads snapshots directly from disk.
- The web dashboard reads published/exported JSON artifacts only.
- Paths may be configured locally via admin tooling to align snapshot locations with operator needs.

The project emphasizes:
- deterministic behavior
- explicit lifecycle control
- platform-specific correctness
- forward extensibility without architectural rewrites

The first implemented and validated platform was **Rumble**.  
Rumble support is currently paused, but all code remains intact and ready for re-enablement.

## Repository Layout

- `core/`: runtime entrypoint (`app.py`), scheduler, job registry, snapshot export loops
- `services/rumble/`: Rumble workers, browser client, SSE client, chat helpers
- `shared/`: platform-neutral configuration, state publishers, storage, logging
- `runtime/`: exported snapshots, manifests, telemetry, and runtime metadata
- `changelog/` + `scripts/`: version stamping and release utilities
- `services/{twitch,youtube,discord}/`: additional platform runtimes and control-plane implementations
- `services/kick/`: Kick chat scaffolding (auth + chat stubs, normalized events) pending scheduler wiring
- `services/pilled/`: ingest-only placeholders; no runtime wiring yet
- `services/chat_replay/`: static chat replay scaffolding shipping exportable HTML surfaces (pop-out window and OBS overlay) with mock data only
  - `contracts/chat_message.schema.json`: placeholder unified chat replay contract
  - `templates/chat_replay_window.html`: standalone replay window (mock data)
  - `templates/chat_overlay_obs.html`: transparent OBS browser-source overlay
  - `templates/partials/theme_selector.html`: theme selection UI stub
  - `static/chat.css`: shared replay styling
  - `static/themes/`: additive theme overrides
  - `static/chat_mock_data.js`: labeled placeholder messages
  - `README.md`: scaffolding documentation and future integration path

### Repository Tree (includes desktop admin scaffolding)
```
StreamSuites/
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── publish-dashboard-state.yml
├── LICENSE
├── README.md
├── RUNTIME_AUDIT_REPORT.md
├── changelog/
│   ├── README.md
│   └── changelog.runtime.json
├── clips/
│   └── output/
│       └── .gitkeep
├── core/
│   ├── README.md
│   ├── __init__.py
│   ├── app.py
│   ├── config_loader.py
│   ├── context.py
│   ├── discord_app.py
│   ├── jobs.py
│   ├── ratelimits.py
│   ├── registry.py
│   ├── scheduler.py
│   ├── state_exporter.py
│   ├── shutdown.py
│   ├── signals.py
│   └── tallies/
│       ├── README.md
│       ├── __init__.py
│       └── models.py
├── data/
│   └── streamsuites.db
├── desktop-admin/
│   ├── StreamSuites.DesktopAdmin.sln
│   ├── StreamSuites.DesktopAdmin/
│   │   ├── App.config
│   │   ├── AboutDialog.cs
│   │   ├── Bridge/
│   │   │   ├── BridgeServer.cs
│   │   │   └── BridgeState.cs
│   │   ├── MainForm.Designer.cs
│   │   ├── MainForm.cs
│   │   ├── MainForm.resx
│   │   ├── Program.cs
│   │   ├── StreamSuites.DesktopAdmin.csproj
│   │   ├── StreamSuites.DesktopAdmin.csproj.user
│   │   └── assets/
│   │       ├── discord-0.svg
│   │       ├── discord-muted.svg
│   │       ├── discord.png
│   │       ├── discord.svg
│   │       ├── kick-0.svg
│   │       ├── kick-muted.svg
│   │       ├── kick.png
│   │       ├── kick.svg
│   │       ├── pilled-0.svg
│   │       ├── pilled-muted.svg
│   │       ├── pilled.png
│   │       ├── pilled.svg
│   │       ├── rumble-0.svg
│   │       ├── rumble-muted.svg
│   │       ├── rumble.png
│   │       ├── rumble.svg
│   │       ├── streamsuites.ico
│   │       ├── twitch-0.svg
│   │       ├── twitch-muted.svg
│   │       ├── twitch.png
│   │       ├── twitch.svg
│   │       ├── twitter-0.svg
│   │       ├── twitter-muted.svg
│   │       ├── twitter.svg
│   │       ├── youtube-0.svg
│   │       ├── youtube-muted.svg
│   │       ├── youtube.png
│   │       └── youtube.svg
│   ├── StreamSuites.DesktopAdmin.Core/
│   │   ├── AppState.cs
│   │   ├── ModeContext.cs
│   │   ├── PathConfigService.cs
│   │   └── StreamSuites.DesktopAdmin.Core.csproj
│   ├── StreamSuites.DesktopAdmin.Models/
│   │   ├── AboutExport.cs
│   │   ├── CreatorsExports.cs
│   │   ├── DataSignalsExports.cs
│   │   ├── DiscordConfigExport.cs
│   │   ├── PlatformStatus.cs
│   │   ├── PlatformExports.cs
│   │   ├── RuntimeSnapshot.cs
│   │   ├── TelemetrySnapshot.cs
│   │   ├── TelemetryExports.cs
│   │   ├── TriggerCounter.cs
│   │   └── StreamSuites.DesktopAdmin.Models.csproj
│   └── StreamSuites.DesktopAdmin.RuntimeBridge/
│       ├── AdminCommandDispatcher.cs
│       ├── FileSnapshotReader.cs
│       ├── JsonExportReader.cs
│       ├── RuntimeConnector.cs
│       └── StreamSuites.DesktopAdmin.RuntimeBridge.csproj
├── desktop-admin/.vs/
│   └── ProjectEvaluation/
│       ├── streamsuites.desktopadmin.metadata.v10.bin
│       ├── streamsuites.desktopadmin.projects.v10.bin
│       └── streamsuites.desktopadmin.strings.v10.bin
├── docs/
│   ├── POST_MORTEM.md
│   └── assets/
│       └── placeholders/
│           ├── daniel-badge.svg
│           ├── daniel.svg
│           ├── hotdog.svg
│           └── streamsuites.svg
├── exports/
│   └── public/
│       └── .gitkeep
├── livechat/
│   ├── index.html
│   ├── livechat.css
│   └── livechat.js
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
├── runtime/
│   ├── admin/
│   │   ├── chat_triggers.json
│   │   ├── creators.json
│   │   ├── integrations.json
│   │   ├── jobs.json
│   │   ├── permissions.json
│   │   └── rate_limits.json
│   ├── exports/
│   │   ├── README.md
│   │   ├── about.admin.json
│   │   ├── about.public.json
│   │   ├── changelog.json
│   │   ├── changelog.runtime.json
│   │   ├── clips.json
│   │   ├── meta.json
│   │   ├── platforms.json
│   │   ├── polls.json
│   │   ├── roadmap.json
│   │   ├── runtime_snapshot.json
│   │   ├── scoreboards.json
│   │   ├── tallies.json
│   │   └── telemetry/
│   │       ├── errors.json
│   │       ├── events.json
│   │       └── rates.json
│   ├── signals/
│   │   ├── chat_events.json
│   │   ├── poll_votes.json
│   │   ├── score_events.json
│   │   └── tally_events.json
│   └── version.py
├── schemas/
│   ├── creators.schema.json
│   ├── discord.schema.json
│   ├── platforms.schema.json
│   ├── system.schema.json
│   └── triggers.schema.json
├── scripts/
│   ├── bootstrap.py
│   ├── publish_state.py
│   ├── update_version.py
│   └── validate_config.py
├── services/
│   ├── chat_api/
│   │   ├── __init__.py
│   │   └── server.py
│   ├── chat_replay/
│   │   ├── README.md
│   │   ├── contracts/
│   │   │   └── chat_message.schema.json
│   │   ├── static/
│   │   │   ├── chat.css
│   │   │   ├── chat_live_input.css
│   │   │   ├── chat_mock_data.js
│   │   │   └── themes/
│   │   │       ├── theme-default.css
│   │   │       ├── theme-midnight.css
│   │   │       └── theme-slate.css
│   │   └── templates/
│   │       ├── chat_overlay_obs.html
│   │       ├── chat_replay_window.html
│   │       ├── chat_window.html
│   │       └── partials/
│   │           ├── footer_live.html
│   │           ├── footer_replay.html
│   │           ├── theme_menu.html
│   │           └── theme_selector.html
│   ├── clips/
│   │   ├── __init__.py
│   │   ├── encoder.py
│   │   ├── exporter.py
│   │   ├── manager.py
│   │   ├── models.py
│   │   ├── storage.py
│   │   ├── uploader.py
│   │   └── worker.py
│   ├── discord/
│   │   ├── README.md
│   │   ├── announcements.py
│   │   ├── client.py
│   │   ├── embeds.py
│   │   ├── commands/
│   │   │   ├── README.md
│   │   │   ├── __init__.py
│   │   │   ├── admin.py
│   │   │   ├── admin_commands.py
│   │   │   ├── creators.py
│   │   │   ├── public.py
│   │   │   └── services.py
│   │   ├── heartbeat.py
│   │   ├── guild_logging.py
│   │   ├── logging.py
│   │   ├── permissions.py
│   │   ├── runtime/
│   │   │   ├── README.md
│   │   │   ├── __init__.py
│   │   │   ├── lifecycle.py
│   │   │   └── supervisor.py
│   │   ├── status.py
│   │   └── tasks/
│   │       ├── README.md
│   │       ├── pilled_live.py
│   │       ├── rumble_live.py
│   │       ├── twitch_live.py
│   │       ├── twitter_posting.py
│   │       └── youtube_live.py
│   ├── kick/
│   │   ├── __init__.py
│   │   ├── README.md
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── chat.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── message.py
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── chat_worker.py
│   │       └── livestream_worker.py
│   ├── pilled/
│   │   ├── README.md
│   │   └── api/
│   │       ├── chat.py
│   │       └── livestream.py
│   ├── rumble/
│   │   ├── api/
│   │   │   ├── channel_page.py
│   │   │   ├── chat.py
│   │   │   └── chat_post.py
│   │   ├── browser/
│   │   │   ├── __init__.py
│   │   │   └── browser_client.py
│   │   ├── chat/
│   │   │   ├── rest_client.py
│   │   │   ├── sse.py
│   │   │   └── tombi_stream.py
│   │   ├── chat_client.py
│   │   ├── models/
│   │   │   ├── chat_event.py
│   │   │   ├── message.py
│   │   │   └── stream.py
│   │   └── workers/
│   │       ├── chat_worker.py
│   │       └── livestream_worker.py
│   ├── triggers/
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   ├── base.py
│   │   ├── README.md
│   │   ├── registry.py
│   │   └── validation.py
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
├── shared/
│   ├── chat/
│   │   └── events.py
│   ├── config/
│   │   ├── chat_behaviour.json
│   │   ├── clip_rules.json
│   │   ├── creators.json
│   │   ├── discord.json
│   │   ├── discord.py
│   │   ├── logging.json
│   │   ├── monetization.json
│   │   ├── posting_rules.json
│   │   ├── ratelimits.json
│   │   ├── services.json
│   │   ├── services.py
│   │   ├── system.json
│   │   ├── system.py
│   │   ├── tiers.json
│   │   └── triggers.json
│   ├── logging/
│   │   ├── levels.py
│   │   └── logger.py
│   ├── platforms/
│   │   ├── __init__.py
│   │   └── state.py
│   ├── public_exports/
│   │   ├── __init__.py
│   │   ├── clips.py
│   │   ├── polls.py
│   │   └── publisher.py
│   ├── ratelimiter/
│   │   └── governor.py
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── admin_contract.py
│   │   ├── chat_context.py
│   │   ├── quotas.py
│   │   ├── quotas_snapshot.py
│   │   ├── hot_reload.py
│   │   └── scoreboards_snapshot.py
│   ├── scoreboards/
│   │   ├── README.md
│   │   ├── placeholders.py
│   │   ├── registry.py
│   │   ├── schema.json
│   │   └── snapshot.py
│   ├── state/
│   │   ├── chat_logs/
│   │   │   └── .gitkeep
│   │   ├── creators/
│   │   │   └── daniel.json
│   │   ├── discord/
│   │   │   ├── README.md
│   │   │   └── runtime.json
│   │   ├── jobs.json
│   │   ├── quotas.json
│   │   ├── scoreboards/
│   │   │   └── .gitkeep
│   │   └── system.json
│   ├── storage/
│   │   ├── chat_events/
│   │   │   ├── __init__.py
│   │   │   ├── index.py
│   │   │   ├── reader.py
│   │   │   ├── schema.json
│   │   │   ├── store.py
│   │   │   └── writer.py
│   │   ├── file_lock.py
│   │   ├── paths.py
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
├── tests/
│   └── __init__.py
├── requirements.txt
├── rumble_chat_poc.py
├── rumble_poc/
├── twitch_chat_poc.py
└── test_rumble_api.py
```

## StreamSuites Desktop Admin (WinForms control plane)

StreamSuites Desktop Admin is a WinForms-based administrator console that reads
runtime-exported snapshots and surfaces platform health, platform enablement,
and telemetry freshness in a native desktop experience. The admin app uses a
Runtime Bridge layer (`StreamSuites.DesktopAdmin.RuntimeBridge`) to read
`runtime_snapshot.json` from the runtime's export directory and projects the
data into a grid with tray-aware health indicators, per-platform inspectors,
and configurable refresh cadences.

- **Purpose:** give operators a lightweight desktop UI that mirrors runtime
  exports without adding new mutation paths. Snapshot reading is isolated in the
  Runtime Bridge (`FileSnapshotReader` + `RuntimeConnector`), and all
  computations are held in `StreamSuites.DesktopAdmin.Core` (`AppState`,
  `ModeContext`).
- **Runtime interaction:** reads snapshot files written by the Python runtime;
  no direct sockets or API calls are required. Platform counts, staleness
  thresholds, and snapshot metadata are displayed inline with color-coded health
  badges and a tray icon.
- **Progress:** `[██████░░░░]` Snapshot reading, grid rendering, and health/tray
  surfacing are live. Runtime lifecycle controls (reserved in
  `RuntimeExecutablePath`) are staged for a later milestone.

### Running runtime + desktop admin together

1. **Start the runtime exports loop:** launch the Python runtime so it keeps
   writing `runtime/exports/runtime_snapshot.json` (for example `python -m
   core.app` or the scheduler entrypoint used in your environment).
2. **Point Desktop Admin at the snapshot directory:** update
   `desktop-admin/StreamSuites.DesktopAdmin/App.config` `SnapshotDirectory`
   to the absolute path of the runtime export root (e.g., the `runtime/exports`
   directory in this repo or a published dashboard checkout such as
   `../StreamSuites-Dashboard/docs/shared/state`). The default file name remains
   `runtime_snapshot.json` but can be overridden via `SnapshotFileName`.
3. **Build and run the WinForms app:** open
   `desktop-admin/StreamSuites.DesktopAdmin.sln` in Visual Studio on Windows and
   run the `StreamSuites.DesktopAdmin` project. The app will refresh snapshots
   on the interval defined by `SnapshotRefreshIntervalMs` and mark stale states
   using `SnapshotStaleAfterSeconds`.

When both processes are active, the desktop admin presents live platform and
telemetry status sourced from the runtime exports while keeping the runtime the
sole authority for state changes.

### Rumble chat ingest modes

- **SSE_BEST_EFFORT (default)**: connects to
  `https://web7.rumble.com/chat/api/chat/<CHAT_ID>/stream` with the live
  browser cookies/headers. HTTP 204 responses are treated as keepalives, not
  failures, and do not trigger exponential backoff. Only `text/event-stream`
  payloads are parsed; non-SSE responses cap retries and cause a downgrade.
- **DOM_MUTATION (authoritative fallback)**: attaches a MutationObserver inside
  the chat iframe to capture newly added message nodes. Each captured node is
  normalized into the runtime message record (username, text, timestamp when
  present) so ingest stays deterministic even when the SSE endpoint is silent
  or blocked. This mode is activated automatically when SSE stays quiet beyond
  the configured window or explicitly fails to connect.
- **DISABLED**: terminal state used when no ingest path can be attached (e.g.,
  chat iframe missing). The worker logs the disabled state but keeps the
  process alive.

The worker logs the active ingest mode at startup and every downgrade event.
DOM send remains isolated and continues regardless of ingest path.

### Chat send (Playwright DOM)

- **Iframe-scoped DOM send**: outbound chat messages target the chat iframe
  directly. The bot focuses `#chat-message-text-input`, dispatches React-safe
  DOM events, and clicks the `button.chat--send` control. **Enter is never
  pressed** to avoid monetization modals or key-capture side effects.
- **Payment / monetization guard**: known Rumble monetization modals are
  detected and closed before sending. All selectors used for sending are logged
  for observability and the send will abort (not fall back to Enter) if
  required elements are missing.
- **No REST chat sends**: outbound chat remains DOM-driven; no REST chat send
  endpoints are used.

## Rumble Chat Ingest Architecture

Rumble chat handling is split into two independent, cooperating paths so that
send reliability is preserved even when ingest requirements change:

- **DOM send (Playwright)**: authenticated browser session drives the chat
  input and button click. This path relies on Playwright only and is unaffected
  by SSE headers or cookies.
- **SSE ingest (httpx)**: authoritative read path that mirrors the browser
  session. The SSE request **must** include the browser's cookies, user-agent,
  Origin `https://rumble.com`, and Referer set to the livestream watch URL.
  Missing any of these headers causes Rumble to return HTTP 204 with
  `content-type=text/html`, which prevents events from flowing.

### Why cookies and headers are required

- Rumble's SSE endpoint validates the authenticated session using both cookies
  and CSRF-style headers derived from the browser context. Cookies alone no
  longer authorize the stream, and requests without the proper User-Agent,
  Origin, and Referer are rejected with empty responses.
- The runtime now exports cookies directly from the Playwright context and
  injects them as both structured cookie jars **and** `Cookie` headers to match
  the browser.

### SSE 204 responses explained

- A 204 response with `content-type=text/html` often means the server is not
  ready to emit events yet. The runtime now treats these as keepalives rather
  than failures and holds the connection without exponential backoff. Only
  repeated non-SSE responses or stream errors trigger a downgrade to the DOM
  mutation ingest path.

### Known limitations

- Rumble SSE availability is environment-dependent; repeated non-SSE responses
  will trigger a downgrade to DOM mutation ingest while HTTP 204 responses are
  treated as keepalives.
- A logged-in Rumble profile is still required in the persistent Playwright
  context before runtime start.
- DOM chat sending requires the chat iframe (`#chat-message-text-input` and
  `button.chat--send`) to be present; if Rumble ships DOM changes, selectors may
  need to be updated before send succeeds.
- Baseline cutoffs prefer DOM-visible timestamps; if both DOM and the
  livestream API are unreachable, the worker falls back to `now()` without
  crashing and keeps ingest mode stateful.
- APIRequestContext is intentionally avoided during ingest to prevent TLS/X509
  crashes and cross-talk with the Playwright automation session; HTTP calls use
  isolated `httpx` clients with browser-derived cookies/headers instead.

## Project Status

- **Status:** Alpha preview, export-driven. Runtime stays authoritative for data snapshots but is not yet connected to the dashboard UI or any live chat socket feeds.
- **Current snapshot:** 0.2.3-alpha (Build 2025.04) remains the active late-alpha reference state.
- **Operational impact:** chat runtime plumbing, live socket ingestion, and overlay feeds are not live; dashboard and overlay views are preview-only and rely on exported/mock data.
- **Dashboard and exports:** schemas and exports continue to be maintained for read-only consumption; UI consumers must not assume live connectivity until runtime wiring is delivered.

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
- **Telemetry snapshots**: `runtime/exports/telemetry/` surfaces read-only
  operational events, rolling rate aggregates, and trimmed error records so the
  dashboard can poll live health signals from static hosting surfaces.

### Version stamping workflow (runtime-owned)

- **Source of truth**: `runtime/version.py` remains the canonical version
  declaration. All downstream JSON surfaces derive from this value.
- **Changelog + roadmap alignment**: `scripts/update_version.py` stamps the
  runtime version across `changelog/changelog.runtime.json`, exported
  changelog files, and the dashboard `version.json` manifest when available.
- **About documentation**: the runtime owns version stamping for the
  dashboard's JSON-driven About content (e.g., `docs/about/about_part*.json`).
  `scripts/update_version.py` updates the `version` field for every About JSON
  document it can find under `<dashboard-root>/about/` while keeping runtime
  execution paths free of About dependencies.
  - **Usage**: `python scripts/update_version.py 0.2.3-alpha --build 2025.04 --dashboard-root ../StreamSuites-Dashboard/docs`
  - If the dashboard checkout is absent, the script safely skips dashboard
    updates while keeping runtime metadata in sync.

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
| `telemetry/events.json` | `runtime/exports/telemetry/` | Public | High-level runtime events (timestamp, source, severity, message). |
| `telemetry/rates.json` | `runtime/exports/telemetry/` | Public | Rolling activity counters for chat, triggers, and actions (60s + 5m windows). |
| `telemetry/errors.json` | `runtime/exports/telemetry/` | Public | Lightweight error records scoped to subsystem/error type without stack traces. |
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
- Rumble Playwright ownership is centralized: `RumbleLivestreamWorker` starts a
  single persistent browser instance, and `RumbleChatWorker` reuses that page
  and chat iframe without opening extra tabs.

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

#### Authoritative Discord guild configuration schema

The single source of truth for per-guild Discord configuration is
`shared/config/discord.json` and is formally defined in
`schemas/discord.schema.json`. All Discord guild-scoped values are nested
under `discord.guilds`, and missing keys default safely (logging disabled,
no channels). Malformed entries are ignored at runtime, and new notification
types can be added without breaking existing configs.

```yaml
discord:
  guilds:
    "123456789012345678":
      logging:
        enabled: false
        channel_id: null
      notifications:
        general: null
        rumble_clips: null
        youtube_clips: null
        kick_clips: null
        pilled_clips: null
        twitch_clips: null
```

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

### Implemented (export-ready)
- Quota enforcement (per-creator/platform, daily, buffer + hard cap)
- Quota snapshot export (runtime cadence → `shared/state/quotas.json`)
- Discord control-plane runtime scaffolding + dashboard state publish
- Twitch and YouTube chat trigger scaffolds (evaluation-only)
- Rumble chat workers (paused, preserved)

### In-flight / hardening
- Harden quota registry wiring across platform workers
- Expand dashboard quota surface for observability only
- Tighten shutdown ordering across runtimes
- Validate YouTube/Twitch trigger scaffolds with live credentials

### Preview / Not Live Yet (dashboard overlays + extensions)
- Chat runtime plumbing — **Not yet live**; dashboard chat/overlay views render preview/mock data only.
- Browser extension feed hydration — **In planning / not started**; extensions continue showing placeholder content until runtime feeds exist.
- OBS overlay runtime feeds — **UI ready / runtime pending**; overlay templates ship mock data only.
- Live chat socket ingestion — **Planned**; no active socket ingestion is wired yet.
- Multi-platform identity routing — **Planned**; identity mapping across platforms is not connected to runtime exports.
- Deterministic replay ingestion — **Planned**; chat replay overlays remain mock-data driven until ingestion wiring lands.

### Longer-term
- Config-driven trigger definitions and cooldown persistence
- Dashboard tooling for creator config introspection (read-only first)
- Additional platform workers (Twitter/X control-plane parity)
- Scheduler telemetry + alert surfaces
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
