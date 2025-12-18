# Discord control-plane runtime

The Discord subsystem is a control-plane runtime only. It does **not** act as a
streaming bot and must never host ingestion logic. Instead, it provides:

- Status reporting for active streaming runtimes
- Admin/config commands for creator-specific settings
- Notifications to operators and parity with future dashboards
- Multi-guild interactions without global identifiers

Design principles:
- Multi-guild support is mandatory; per-guild contexts and state must be used
  instead of global IDs.
- The Discord runtime should surface control-plane features that mirror the
  operator dashboard (GitHub Pages initially, Wix Studio later) without
  coupling to streaming workers.
- Core streaming logic remains in `core/app.py` and platform services; Discord
  merely observes and coordinates through explicit interfaces.
