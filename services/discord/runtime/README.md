# Discord runtime lifecycle (scaffold)

This package hosts the lifecycle scaffolding for the Discord control-plane
runtime. No business logic lives here; its purpose is to coordinate process
health and lifecycle hooks for the Discord bot.

- `supervisor.py` owns startup, reconnect, and shutdown orchestration for the
  Discord runtime. It keeps control-plane processes isolated from streaming
  ingestion and is responsible for restartability.
- `lifecycle.py` provides lifecycle hooks that replace raw `discord.py` events
  with structured callbacks for supervisors or higher-level controllers.
- `__init__.py` is intentionally minimal, exposing the package boundary without
  side effects.

All future logic should respect these boundaries and avoid embedding Discord
business behavior inside the lifecycle scaffolding.
