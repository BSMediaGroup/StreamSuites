# Discord control-plane runtime

The Discord subsystem is a **control-plane runtime**. It provides operational
commands, status reporting, and notifications without embedding any streaming
ingestion logic. It can run as:

- **Standalone process**: `python -m core.discord_app` for direct execution.
- **Scheduler-integrated**: started by `core.scheduler` when Discord is enabled
  in `shared/config/creators.json`. In integrated mode it must **not** create
  its own event loop.

The runtime is process-scoped and parallel to streaming runtimes. It never owns
streaming workers or scheduler control and can be restarted independently.

## Architecture

- **DiscordClient (`services/discord/client.py`)**
  - Owns the Discord connection and slash command registration surface.
  - No control-flow logic; delegates to supervisors and handlers.
- **DiscordSupervisor (`services/discord/runtime/supervisor.py`)**
  - Owns lifecycle orchestration, startup/shutdown coordination, and background
    task supervision for the Discord process.
  - Ensures no event loop is created when integrated with `core.scheduler` and
    enforces clean shutdown semantics.
- **Heartbeat (`services/discord/heartbeat.py`)**
  - Periodic liveness signaling owned by the supervisor.
- **Status persistence (`services/discord/status.py`)**
  - Writes shared state for other control/monitoring surfaces.
- **Permissions (`services/discord/permissions.py`)**
  - Uses Discord-native admin flags for privileged commands; no custom ACL
    layer is introduced.
- **Logging (`services/discord/logging.py`)**
  - Centralizes control-plane logging adapters; no side effects on import.
- **Announcements/notifications (`services/discord/announcements.py`)**
  - Routed through the control-plane runtime only; streaming runtimes remain
    separate.

### Command surface layering

- **Handlers (pure logic)**
  - `commands/admin.py` contains admin handlers with no Discord I/O primitives.
  - `commands/services.py` contains service-level control-plane handlers.
- **Registration/wiring**
  - Slash command registration modules (e.g., an `admin_commands.py` surface)
    wire Discord slash commands to handlers only.
  - Additional registration modules follow the same pattern: wire slash
    commands to handler functions without embedding business logic.

### Runtime rules

- No streaming workers are launched from this runtime.
- No event loop creation when started by `core.scheduler`.
- No scheduler logic is embedded; scheduling remains owned by `core/app.py` and
  `core/scheduler.py`.
- Modules must avoid side effects on import to keep the control-plane runtime
  deterministic and restartable.

## Directory scaffold

```text
services/discord/
├── README.md                 # This file: control-plane architecture and rules
├── announcements.py          # Notification routing (control-plane only)
├── client.py                 # DiscordClient connection + command surface
├── commands/                 # Layered command handlers and registration
├── heartbeat.py              # Heartbeat loop owned by the supervisor
├── logging.py                # Logging adapters (no side effects on import)
├── permissions.py            # Admin gating via Discord-native flags
├── runtime/                  # Lifecycle management and supervisor scaffolding
├── status.py                 # Shared-state status persistence
└── tasks/                    # Control-plane initiated task helpers
```
