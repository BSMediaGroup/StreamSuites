# Discord runtime lifecycle

This package hosts lifecycle management for the Discord control-plane runtime.
It is responsible for process-scoped orchestration and does not host streaming
logic or scheduler ownership.

- `supervisor.py`
  - Owns startup, reconnection, heartbeat scheduling, and shutdown coordination
    for the Discord runtime.
  - Manages background tasks created by the control-plane runtime and ensures
    they are supervised and cancelled on shutdown.
  - Guarantees that no event loop is created when `core.scheduler` instantiates
    the runtime; it binds to the scheduler-owned loop instead.
- `lifecycle.py`
  - Provides structured lifecycle hooks that wrap `discord.py` events for use by
    the supervisor and higher-level controllers.
- `__init__.py`
  - Minimal package surface with no import side effects.

Shutdown guarantees: the supervisor coordinates cancellation of background
tasks, heartbeat teardown, and client disconnect to keep the control-plane
runtime restartable without impacting streaming runtimes.
