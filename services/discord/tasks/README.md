# Discord control-plane tasks

Helpers under `tasks/` are invoked by the Discord control-plane runtime to
trigger platform actions (notifications, live-state checks, etc.). They do not
create streaming workers and must remain import-safe so the scheduler can start
the Discord runtime without side effects.
