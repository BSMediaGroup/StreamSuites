# Runtime Audit Report — StreamSuites Runtime (v0.2.2-alpha)

## 1) Current platform status (authoritative)
- **YouTube** — Active polling chat worker with quota-aware loop and trigger
  evaluation; now registers a validation trigger to emit deterministic
  `validation_passed` actions. 【F:services/youtube/workers/chat_worker.py†L1-L78】【F:services/triggers/validation.py†L1-L26】
- **Twitch** — Active IRC chat worker; continues to reply to `!ping` and now
  registers the validation trigger to prove trigger → action → export flow. 【F:services/twitch/workers/chat_worker.py†L1-L86】【F:services/triggers/validation.py†L1-L26】
- **Rumble** — Paused; Playwright/SSE workers retained but not orchestrated due
  to unstable chat_id discovery. Missing credentials/config now surface
  runtime_state errors without breaking startup. 【F:README.md†L28-L52】【F:core/scheduler.py†L186-L248】
- **Kick** — Scheduler feature-flag now starts the stub chat worker (offline),
  exercising NonEmptyChatValidationTrigger and action counters when env creds
  are present; missing creds surface non-fatal errors. 【F:core/scheduler.py†L300-L360】【F:services/kick/workers/chat_worker.py†L1-L79】
- **Pilled** — Planned ingest-only; placeholders kept to preserve interfaces for
  future lightweight client. 【F:services/pilled/README.md†L1-L15】【F:services/pilled/api/chat.py†L1-L9】

## 2) Why triggers/jobs are idle (not broken)
- **Triggers**: Registry exists and processes events. The new
  `NonEmptyChatValidationTrigger` proves matching/action emission for any
  non-empty chat text, but no executor persists or dispatches actions beyond
  logging/state counters. Idle state stems from missing downstream action
  execution and the absence of live chat ingress beyond YouTube/Twitch stubs.
- **Jobs**: Job registry and clip jobs remain feature-gated; no producer feeds
  are currently generating job requests. Idle condition is intentional to avoid
  executing side effects while live ingestion is incomplete.

## 3) Minimal functional runtime (concrete definition)
A minimally functional runtime for StreamSuites is achieved when:
1. **Platform ingestion**: At least one active platform (YouTube/Twitch/Kick
   stub) can connect/poll and emit normalized chat events into runtime_state.
2. **Trigger loop**: Registered triggers evaluate incoming events and emit
   action descriptors (e.g., `validation_passed`) without crashing workers.
3. **State export**: Runtime exports (platform status + telemetry) update on a
   deterministic cadence for dashboard consumers (file-based snapshots are
   sufficient while dashboards remain read-only).
4. **Graceful lifecycle**: Workers and scheduler can start/stop cleanly without
   orphaned connections or hung tasks.

## 4) Triggers & Jobs — validation path
- Implemented **NonEmptyChatValidationTrigger** (matches any non-empty chat
  message) and registered it in YouTube, Twitch, and Kick workers to emit
  deterministic `validation_passed` actions. 【F:services/triggers/validation.py†L1-L26】【F:services/kick/workers/chat_worker.py†L21-L79】
- This proves end-to-end trigger flow: synthetic Kick messages and live
  YouTube/Twitch ingress both pass through the registry, increment trigger
  counters, and optionally hand actions to the ActionExecutor hook.

## 5) Runtime ↔ Dashboard gap (file-backed hot reload now optional)
- Dashboard still reads static JSON (e.g., `StreamSuites-Dashboard/docs/shared/state/runtime_snapshot.json`), but a new optional
  `HotReloadWatcher` can re-publish runtime snapshots + telemetry whenever files under `runtime/exports/` change. It is disabled
  by default, bounded by a configurable interval, and driven by `system.hot_reload` in `shared/config/system.json`. 【F:core/hot_reload_watcher.py†L1-L90】【F:runtime/exports/README.md†L9-L21】【F:shared/config/system.json†L2-L22】

## 6) Roadmap + documentation placements
- About exports list platform statuses and now track the planned Desktop Admin EXE control plane for parity planning. 【F:runtime/exports/about.public.json†L1-L23】【F:runtime/exports/about.admin.json†L1-L23】
- `platforms.json` notes Kick’s scheduler wiring under a feature flag and keeps Rumble paused. 【F:runtime/exports/platforms.json†L1-L13】
- Roadmap adds a desktop-admin/local control surface entry alongside existing ingestion items. 【F:runtime/exports/roadmap.json†L1-L118】

## 7) Desktop Admin control plane readiness
- System config now carries an explicit hot-reload toggle + watch path to bound file-based admin writes; runtime_state ingests it
  alongside platform flags to preserve deterministic startup/shutdown. 【F:shared/config/system.py†L31-L86】【F:core/app.py†L22-L120】
- Control-plane expectations are documented via about/roadmap exports so the Desktop Admin EXE can rely on file-based exports
  first, with future IPC/HTTP hooks added later. 【F:runtime/exports/about.admin.json†L13-L23】【F:runtime/exports/roadmap.json†L1-L118】
- Desktop Admin EXE is positioned as a local control surface: runtime remains authoritative, dashboard stays read-only, and any
  future write paths must stay within the documented file-based boundaries until IPC/HTTP parity is validated. 【F:RUNTIME_AUDIT_REPORT.md†L1-L120】

## 8) Implementation prompt (next Codex session — enriched)
```
You are implementing StreamSuites Runtime (v0.2.2-alpha) based on this audit.

Goals:
1) Keep Kick chat scaffold feature-flagged in core scheduler: start the stub chat worker only when `system.platforms.kick`
   is enabled, use env creds (client ID/secret/username/bot name) without logging secrets, and treat the client as offline
   while still emitting normalized chat events + NonEmptyChatValidationTrigger actions into runtime_state.
2) Maintain trigger visibility across YouTube/Twitch/Kick by keeping `NonEmptyChatValidationTrigger` registered and surfacing
   runtime_state counters/telemetry in `runtime/exports/platforms.json` and dashboard consumers (e.g.,
   StreamSuites-Dashboard/docs/js/platforms/kick.js and twitch.js readers of export snapshots).
3) Preserve Rumble paused: record paused status + paused_reason, guard against missing `rumble_manual_watch_url` or
   `rumble_livestream_api_env_key` without fatal errors, and avoid starting workers.
4) Keep the optional HotReloadWatcher disabled by default but available via `shared/config/system.json` (`system.hot_reload`):
   monitor `runtime/exports/` (configurable), debounce via bounded intervals, and re-publish runtime_snapshot + telemetry that
   downstream dashboards read from `runtime/exports/*.json` / StreamSuites-Dashboard/docs/shared/state/*.json. No secrets in logs; no
   unbounded polling loops.
5) Document/Desktop Admin EXE readiness: continue publishing about/roadmap control-plane notes, keep restart-applied config
   hashes intact, and describe file-based + future local IPC/HTTP interaction so the Desktop Admin EXE can manage configs
   without mutating dashboard-controlled data.

Guardrails: deterministic startup/shutdown, feature flags only, no breaking changes to existing bots, and no secret logging.
```
