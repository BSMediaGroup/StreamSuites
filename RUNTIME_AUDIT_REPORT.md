# Runtime Audit Report — StreamSuites Runtime

## 1. Current Runtime State (Factual)
- **Core runtime** (`core/`): Entrypoint boots config loader, scheduler, job registry, clip runtime, and periodic snapshot loops for runtime and quota exports.【F:core/app.py†L34-L144】【F:core/state_exporter.py†L215-L247】
- **Scheduler** (`core/scheduler.py`): Orchestrates per-creator runtimes, starting platform workers for Rumble (browser/SSE ingest), Twitch (IRC), and YouTube (API polling) based on platform enablement and environment credentials; maintains heartbeat and quota snapshot cadence.【F:core/scheduler.py†L98-L228】【F:core/scheduler.py†L290-L354】
- **Job system** (`core/jobs.py`): Provides job registry and asynchronous execution with metrics and persistence hooks; clip jobs are registered when enabled by creator features.【F:core/jobs.py†L12-L198】【F:core/app.py†L75-L90】
- **Configuration ingestion** (`core/config_loader.py`): Loads dashboard-compatible `creators.json` and `platforms.json`, validates when schemas available, and falls back to `services.json` toggles.【F:core/config_loader.py†L27-L173】
- **Runtime state export** (`core/state_exporter.py`): Tracks per-creator platform status and rumble chat ingest status, writes `runtime_snapshot.json` via `DashboardStatePublisher`, and preserves file-based exports for downstream dashboard readers.【F:core/state_exporter.py†L45-L213】【F:core/state_exporter.py†L236-L247】
- **Exports & signals** (`runtime/exports`, `runtime/signals`, `runtime/admin`): Pre-generated JSON snapshots for changelog, polls, tallies, scoreboards, clips, admin manifests, and signal logs remain as static artifacts.【F:runtime/exports/README.md†L1-L21】【F:runtime/signals/chat_events.json†L1-L17】【F:runtime/admin/chat_triggers.json†L1-L41】
- **Chat replay scaffolding** (`services/chat_replay/`): Static pop-out and OBS overlay HTML surfaces ship with mock data and a schema-backed replay message model; they are export-safe and non-interactive until runtime replay ingestion exists.【F:services/chat_replay/README.md†L1-L24】【F:services/chat_replay/templates/chat_replay_window.html†L1-L64】
- **Platform services** (`services/`):
  - **YouTube**: Chat worker polls live chat via API key, enforces quotas when configured, and routes normalized events to trigger registry.【F:services/youtube/workers/chat_worker.py†L18-L125】
  - **Twitch**: Chat worker connects over IRC/TLS using env credentials, logs messages, evaluates triggers, and supports basic builtin ping response.【F:services/twitch/workers/chat_worker.py†L12-L126】
  - **Rumble (DEFERRED)**: Livestream worker controls Playwright browser session and spawns chat worker that captures EventSource stream, maintains DOM send path, persists chat IDs, and records ingest status.【F:services/rumble/workers/livestream_worker.py†L12-L120】【F:services/rumble/workers/chat_worker.py†L91-L360】
  - **Triggers**: Registry manages per-creator triggers; base class defines pure matching/action contract (execution not implemented).【F:services/triggers/registry.py†L9-L57】【F:services/triggers/base.py†L5-L30】
  - **Other services**: Discord supervisor intentionally disabled in scheduler; Twitter/pilled components present in services folder but not invoked by core scheduler.【F:core/scheduler.py†L232-L245】【F:README.md†L53-L65】
- **Ingestion paths**:
  - **YouTube**: Polling via `YouTubeChatClient.iter_messages()` using `live_chat_id` discovered per creator; quota enforcement optional per limits config.【F:core/scheduler.py†L181-L224】【F:services/youtube/workers/chat_worker.py†L18-L115】
  - **Twitch**: IRC read loop via `TwitchChatClient.iter_messages()` with optional send helper; minimal builtin triggers only.【F:core/scheduler.py†L144-L177】【F:services/twitch/workers/chat_worker.py†L54-L126】
  - **Rumble (Deferred)**: Browser EventSource tap with DOM send; chat ID tracking/persistence and reconnect logic around Playwright page reloads.【F:services/rumble/workers/chat_worker.py†L125-L360】
- **Trigger system status**: Trigger registry exists and processes events, but only emits action descriptors; no downstream execution wiring present.【F:services/triggers/registry.py†L36-L57】
- **Job system status**: Clip jobs are feature-gated; job registry counts metrics and persists job lifecycle via state store hooks.【F:core/app.py†L75-L90】【F:core/jobs.py†L99-L198】
- **Export/telemetry status**: Runtime snapshot and quota snapshot publishers run periodic loops; telemetry uses runtime state for platform/creator and rumble chat ingest status.【F:core/app.py†L92-L144】【F:core/state_exporter.py†L151-L213】
- **Scheduler/lifecycle status**: Entrypoint installs signal handlers, runs until stop event, cancels tasks, and performs orderly shutdown including browser client teardown if Rumble started.【F:core/app.py†L146-L265】【F:core/scheduler.py†L318-L355】

## 2. Known Failure Modes & Instability
- **Rumble chat ingestion instability (suspension cause)**: README notes inability to deterministically discover or sustain `chat_id`, inconsistent endpoints, and failed remediation, leading to indefinite suspension.【F:README.md†L10-L24】【F:README.md†L49-L154】
- **Rumble browser stream disconnects**: Chat worker treats 30s idle from EventSource tap as disconnection, triggering reload/backoff; repeated disconnects can halt ingest and record failure in runtime state.【F:services/rumble/workers/chat_worker.py†L338-L360】【F:services/rumble/workers/chat_worker.py†L326-L334】
- **Chat ID persistence brittleness**: Chat worker writes `shared/config/creators.json`; failures to read/write log errors but do not recover, leaving chat ID unset and ingest status potentially stale.【F:services/rumble/workers/chat_worker.py†L232-L275】
- **Coupling to scheduler/runtime state**: Rumble ingest updates shared runtime state; exceptions during worker startup propagate to scheduler and can mark platform error, impacting global snapshot status.【F:core/scheduler.py†L119-L142】【F:core/state_exporter.py†L151-L213】
- **YouTube dependency on environment keys**: Scheduler raises runtime error when YouTube enabled without API key, preventing creator runtime start.【F:core/scheduler.py†L183-L227】
- **Twitch dependency on env credentials**: Missing OAuth token/channel raise runtime error when Twitch enabled, blocking runtime for that creator.【F:core/scheduler.py†L146-L177】

## 3. Architectural Health Check
- **Module boundaries**: Core orchestrates lifecycle and exports; services house platform-specific workers; triggers are isolated; jobs handle async tasks — boundaries generally clear (SAFE).【F:core/app.py†L34-L144】【F:services/twitch/workers/chat_worker.py†L12-L126】
- **Responsibility separation**: Scheduler manages platform startups and heartbeats while workers encapsulate platform logic; Discord intentionally disabled — separation holds (SAFE).【F:core/scheduler.py†L98-L245】
- **Runtime vs dashboard contract**: Runtime owns snapshot generation for dashboard; dashboard is read-only. Contract documented and enforced via `DashboardStatePublisher` usage (SAFE).【F:README.md†L156-L200】【F:core/state_exporter.py†L215-L247】
- **Configuration loading patterns**: Config loader tolerates missing files and validates optionally; falls back to legacy services config — flexibility may hide config errors (QUESTIONABLE).【F:core/config_loader.py†L55-L173】
- **Error handling consistency**: Workers often catch/log exceptions and continue; some propagate (YouTube/Twitch env errors, Rumble startup) leading to hard failures — mixed consistency (QUESTIONABLE).【F:core/scheduler.py†L119-L227】【F:services/rumble/workers/chat_worker.py†L326-L334】
- **Logging consistency**: Logging present across core and workers with structured creator context; some logs elevated to warning/error appropriately (SAFE).【F:services/twitch/workers/chat_worker.py†L54-L110】【F:core/app.py†L41-L108】

## 4. Technical Debt & Housekeeping (Non-Destructive)
- **Dead/unused code**: Discord supervisor and Twitter/pilled services present but not invoked by scheduler; remain dormant.【F:core/scheduler.py†L232-L245】【F:README.md†L53-L65】
- **Redundant logic paths**: Rumble chat worker both reloads page after tap and revalidates chat ready during reconnect loop; potential duplication in recovery handling.【F:services/rumble/workers/chat_worker.py†L292-L360】
- **Legacy naming**: `services.json` fallback remains alongside `platforms.json`, signaling transition state between config schemas.【F:core/config_loader.py†L140-L173】
- **Missing documentation**: Trigger actions lack execution pipeline; no docs indicating expected downstream consumer; service layout only briefly described in repository overview.【F:services/triggers/registry.py†L36-L57】【F:README.md†L53-L65】
- **Inconsistent config schemas**: Creator/platform enablement can be booleans, dicts, or lists; normalization attempts exist but allow varied shapes (QUESTIONABLE).【F:core/state_exporter.py†L70-L102】【F:core/config_loader.py†L95-L173】

## 5. Beta Pathway (Post-Rumble-Deferred)
- **Must work for beta**:
  - Stable YouTube chat polling with quota enforcement per creator, including trigger evaluation and export visibility.【F:services/youtube/workers/chat_worker.py†L18-L125】【F:core/state_exporter.py†L151-L213】
  - Functional Twitch chat ingestion and basic send path with trigger routing; heartbeat and telemetry reflected in runtime snapshot.【F:services/twitch/workers/chat_worker.py†L12-L126】【F:core/scheduler.py†L144-L177】
  - Centralized trigger registry producing deterministic action descriptors for both platforms; runtime snapshot export loops running reliably.【F:services/triggers/registry.py†L36-L57】【F:core/app.py†L92-L144】
  - Job system operational for enabled clip features with quota checks where configured.【F:core/jobs.py†L99-L198】【F:core/app.py†L75-L90】
- **May be deferred**:
  - Discord control-plane runtime and Twitter/Pilled services not currently orchestrated by scheduler.【F:core/scheduler.py†L232-L245】【F:README.md†L53-L65】
  - Advanced trigger action execution (beyond action descriptors) pending executor design.【F:services/triggers/registry.py†L36-L57】
- **Must be frozen**:
  - Rumble ingestion remains disabled operationally but code retained; avoid changes that break future parity paths.【F:README.md†L49-L154】【F:services/rumble/workers/livestream_worker.py†L12-L120】
- **Must be deterministic**:
  - Snapshot publishing cadence, heartbeat updates, and quota aggregation loops must maintain fixed intervals and error handling to prevent telemetry drift.【F:core/app.py†L110-L144】【F:core/scheduler.py†L290-L354】

## 6. Rumble Re-Integration Strategy (Future)
- **Preconditions**: Deterministic `chat_id` discovery and stable EventSource responses; reliable read/write of creators config for chat ID persistence; validated selectors for DOM send path.【F:README.md†L67-L148】【F:services/rumble/workers/chat_worker.py†L232-L360】
- **Parity expectations**: Match YouTube/Twitch behavior with trigger routing and runtime telemetry updates without leaking failures into other platforms; scheduler start/stop semantics consistent across platforms.【F:core/scheduler.py†L98-L177】【F:core/state_exporter.py†L151-L213】
- **Guardrails before enabling**: Isolation of Rumble failures from global runtime shutdown, backoff limits for reconnect loops, validation of chat ID persistence writes, and telemetry flags to mark deferred/experimental status.【F:services/rumble/workers/chat_worker.py†L338-L360】【F:core/state_exporter.py†L151-L213】

## 7. Final Output: Implementation Prompt (Do Not Execute)

=== FUTURE CODEX IMPLEMENTATION PROMPT (DO NOT EXECUTE) ===
You are tasked with implementing the beta pathway for StreamSuites Runtime with Rumble deferred. Follow these guardrails:
- Preserve existing Rumble code paths but keep them disabled operationally; ensure scheduler tolerates absent Rumble credentials without impacting YouTube/Twitch startups.【F:core/scheduler.py†L119-L177】
- Harden YouTube and Twitch chat workers: ensure environment validation, stable polling/IRC loops, and trigger evaluation emit deterministic action descriptors; add telemetry for failures without crashing the runtime loops.【F:services/youtube/workers/chat_worker.py†L18-L125】【F:services/twitch/workers/chat_worker.py†L54-L126】
- Maintain periodic runtime and quota snapshot publishing intervals; ensure heartbeat updates reflect platform status accurately even when triggers/jobs are idle.【F:core/app.py†L110-L144】【F:core/scheduler.py†L290-L354】
- Keep job registry behavior intact while enabling clip jobs only when configured; surface job metrics in exports without altering persistence schema.【F:core/app.py†L75-L90】【F:core/jobs.py†L99-L198】
- Design trigger action execution layer (separate from registry) that consumes emitted descriptors without modifying registry semantics; ensure actions remain platform-agnostic and auditable.【F:services/triggers/registry.py†L36-L57】
- Prior to re-enabling Rumble, implement feature flagging, robust chat ID persistence checks, bounded reconnect/backoff, and telemetry isolation so failures do not mark global runtime error states.【F:services/rumble/workers/chat_worker.py†L232-L360】【F:core/state_exporter.py†L151-L213】
