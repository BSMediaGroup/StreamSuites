# Core runtimes

This repository now supports multiple runtime entrypoints while remaining a
single canonical source for streaming automation. Two primary supervisors live
in `core/`:

- `app.py` – streaming runtime supervisor responsible for orchestrating
  ingestion workers, scheduling, and lifecycle management for platform data
  plane tasks.
- `discord_app.py` – Discord control-plane runtime supervisor placeholder. This
  runtime will handle Discord command and control flows independently of the
  streaming runtime and will be wired with its own lifecycle, logging, and
  restartability. It shares `shared/` configuration/state and `services/`
  modules but must not launch streaming ingestion workers.

Both entrypoints are valid, independent runtimes that draw from the same shared
modules to enforce consistent behavior and configuration across platforms.

## Rumble runtime status

Rumble chat workers and related services remain in the codebase but are
currently **paused** due to upstream API protection and DDoS mitigation
measures. No functionality has been removed; re-enablement is expected once
official API access or whitelisting is available. The paused state is
intentional to preserve compatibility and future readiness.
