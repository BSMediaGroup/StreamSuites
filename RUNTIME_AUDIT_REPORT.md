# Runtime Audit Report — StreamSuites Runtime (v0.2.2-alpha)

## 1) Current platform status (authoritative)
- **YouTube** — Active polling chat worker with quota-aware loop and trigger
  evaluation; now registers a validation trigger to emit deterministic
  `validation_passed` actions. 【F:services/youtube/workers/chat_worker.py†L1-L78】【F:services/triggers/validation.py†L1-L26】
- **Twitch** — Active IRC chat worker; continues to reply to `!ping` and now
  registers the validation trigger to prove trigger → action → export flow. 【F:services/twitch/workers/chat_worker.py†L1-L86】【F:services/triggers/validation.py†L1-L26】
- **Rumble** — Paused; Playwright/SSE workers retained but not orchestrated due
  to unstable chat_id discovery. 【F:README.md†L28-L52】【F:services/rumble/workers/livestream_worker.py†L1-L35】
- **Kick** — New scaffold mirrors other platforms: env-checked auth stub,
  simulated chat client, normalized event shape, trigger wiring, and runtime
  heartbeat/telemetry hooks. Not yet wired into scheduler. 【F:services/kick/api/chat.py†L1-L86】【F:services/kick/workers/chat_worker.py†L1-L79】
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

## 5) Runtime ↔ Dashboard gap (why static GitHub JSON blocks ops)
- The dashboard reads static JSON from GitHub Pages; runtime changes are not
  reflected until files are manually regenerated and published. No hot reload or
  control-plane API exists, so dashboard controls cannot start/stop workers or
  surface live telemetry.
- **Minimal solution (file-backed hot reload watcher)**: Add a lightweight
  runtime-side watcher that reloads config/exports from a local directory and
  republishes `runtime/exports/*.json` when files change. Dashboard operators can
  drop updated JSON locally without GitHub latency; runtime emits fresh exports
  the watcher can also expose over localhost for future UI polling.

## 6) Roadmap + documentation placements
- About exports now list platform statuses including Kick scaffold and Pilled
  planned ingest-only. 【F:runtime/exports/about.public.json†L1-L19】【F:runtime/exports/about.admin.json†L1-L19】
- A new `platforms.json` state export captures active/paused/scaffold/planned
  modes for YouTube, Twitch, Rumble, Kick, and Pilled. 【F:runtime/exports/platforms.json†L1-L16】
- Roadmap retains existing items; Kick/Pilled planning is documented via the new
  platform export and about manifests, keeping dashboard consumers aware of
  future platforms.

## 7) Implementation prompt (ready for next Codex session)
```
You are implementing StreamSuites Runtime (v0.2.2-alpha) based on the latest
runtime audit.

Goals:
1) Wire the new Kick scaffold into core/scheduler with a feature flag so it can
   run the stub chat worker without impacting other platforms. Use the existing
   env vars (client ID/secret, username, bot name) but never log secrets. Treat
   the chat client as offline; just exercise trigger + runtime_state updates.
2) Add a file-backed hot reload watcher that detects changes under a configurable
   directory (default: runtime/exports/) and republishes exports/telemetry to the
   dashboard-friendly JSON files. Keep it optional and disabled by default.
3) Preserve Rumble as paused; do not enable its workers. Ensure scheduler
   handles missing Rumble credentials without fatal errors.
4) Keep the `NonEmptyChatValidationTrigger` registered for YouTube/Twitch/Kick
   and surface emitted actions through runtime_state counters for visibility.
5) Maintain deterministic shutdown and logging; avoid introducing side effects
   or non-deterministic retries.

Deliverables: scheduler flag + Kick worker wiring, hot reload watcher module with
minimal tests or manual steps, and updated exports/README documenting how the
watcher is toggled and where new platform status is surfaced.
```
