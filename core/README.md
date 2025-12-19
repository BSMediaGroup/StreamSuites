# Core runtimes

This repository supports multiple runtime entrypoints while remaining a single
canonical source for streaming automation. Two primary supervisors live in
`core/`:

- `app.py` – streaming runtime supervisor responsible for orchestrating
  ingestion workers, scheduling, and lifecycle management for platform data
  plane tasks. It owns the event loop, scheduler, and coordinated shutdown of
  all streaming runtimes.
- `discord_app.py` – Discord control-plane runtime entrypoint. This process is
  process-scoped (one per control-plane runtime) and runs either standalone
  (`python -m core.discord_app`) or integrated when `core.scheduler` is
  configured to start Discord. It owns Discord command/control flows without
  launching streaming ingestion workers or creating its own event loop when
  started by the scheduler.

Both entrypoints are valid, independent runtimes that draw from the same shared
modules to enforce consistent behavior and configuration across platforms.

## Ownership boundaries

- `core/app.py` contains the authoritative event loop, scheduler orchestration,
  and shutdown controls for streaming runtimes.
- The Discord runtime can be started by the scheduler when enabled in
  `shared/config/creators.json` or by running `python -m core.discord_app`
  directly. In integrated mode it must not create its own loop and remains
  isolated and independently restartable.
- `core/app.py` must not contain Discord-specific logic; Discord behaviors live
  under `services/discord/` and are invoked through explicit orchestration
  rather than embedded imports.
- Twitch chat foundations live under `services/twitch/`; the scheduler will own
  lifecycle once the platform is feature-flagged for creators. The Twitch
  worker remains idle until explicitly started, keeping parity with the
  existing Discord separation.

## Rumble runtime status

Rumble chat workers and related services remain in the codebase but are
currently **paused** due to upstream API protection and DDoS mitigation
measures. No functionality has been removed; re-enablement is expected once
official API access or whitelisting is available. The paused state is
intentional to preserve compatibility and future readiness.
