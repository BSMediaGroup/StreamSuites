# Scoreboards (Foundational Scaffolding)

This folder introduces the initial runtime scaffolding for scoreboard concepts.
Mechanics, scoring math, and platform-specific behaviour are intentionally left
undefined. The runtime remains authoritative for any stored state, while the
future dashboard will consume read-only snapshots derived from the runtime.

## Intent
- Define placeholders for scoreboard types and participating modules.
- Establish a canonical JSON shape for scoreboard entries.
- Provide snapshot helpers for dashboard consumption without mutating runtime
  data during reads.

## Non-goals (yet)
- No gameplay logic, no scoring algorithms, no randomization engines.
- No enforcement or balance rules.
- No persistence writes beyond state publisher hooks.

## Files
- `schema.json`: Canonical, versioned scoreboard entry contract.
- `registry.py`: Registers scoreboard types and emitting modules (no math).
- `snapshot.py`: Builds read-only runtime snapshots for dashboard sync.
- `placeholders.py`: Explicit TODO markers for future mechanics and detection
  hooks.

All functionality not yet designed is marked as a placeholder to ensure future
extensions remain additive and non-destructive.
