# Discord state storage

This directory stores per-guild JSON configuration and runtime data for the
Discord control-plane runtime. Each guild receives its own namespace to avoid
global identifiers and to guarantee multi-guild safety.

Design goals:
- Per-guild JSON configuration files stored under `guilds/` to isolate settings
  and credentials.
- Parity between dashboard configuration (GitHub Pages initially, Wix Studio
  later) and Discord bot state so operators can manage settings in either
  surface without divergence.
- Potential for hot-reload of configuration in the future; file formats should
  remain declarative to make this feasible without code changes.

The control-plane runtime publishes a live snapshot for the dashboard at
`shared/state/discord/runtime.json`. The dashboard will fall back to the raw
GitHub URL for this repository if a local `shared/state/` is not available, so
the snapshot is committed here to guarantee a default source of truth even when
the runtime is not actively mirroring to the dashboard checkout.
