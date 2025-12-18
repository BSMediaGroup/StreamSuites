"""Discord runtime entrypoint (control-plane only).

This module is a dedicated supervisor entrypoint for the Discord
control-plane runtime. It will eventually:
- manage Discord command and event handling separately from the streaming runtime
- own its lifecycle, logging, and restartability
- share shared/ state, schemas, and services/ modules with other runtimes

Important notes:
- This runtime is control-plane only and MUST NOT launch streaming ingestion workers.
- Streaming runtime responsibilities remain with core/app.py.
- All implementations are intentionally TODO placeholders to keep the scaffold aligned
  with the multi-runtime architecture.

TODO: Implement Discord runtime bootstrap, logging, and supervisor wiring.
TODO: Integrate shared services without duplicating streaming ingestion behavior.
"""


if __name__ == "__main__":
    # TODO: Wire the Discord runtime supervisor entrypoint.
    pass
