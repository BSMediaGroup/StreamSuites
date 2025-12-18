# Discord command layering

This package defines Discord command surfaces for the control-plane runtime.
Design rules:

- Handler modules (`admin.py`, `services.py`, etc.) contain pure logic with no
  direct Discord I/O primitives.
- Registration modules (`admin_commands.py` or similar) wire slash commands to
  handlers only; no business logic should be added there.
- Modules must remain import-safe (no side effects) so the runtime can load
  commands during supervisor-controlled startup without creating event loops.
