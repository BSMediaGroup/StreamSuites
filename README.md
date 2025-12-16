# StreamSuites

StreamSuites is a modular, multi-platform livestream automation system
designed to provide reliable, extensible tooling for creators operating
across platforms such as Rumble, YouTube, Twitch, Discord, and others.

The project is built with a strong emphasis on:
- deterministic behavior
- clean lifecycle management
- platform-specific correctness
- future extensibility without architectural rewrites

The first implemented and validated platform is **Rumble**.

---

## Current Status

**Beta Prebuild – Core Runtime Proven**

The system currently supports:
- Verified Rumble livestream chat reading via official livestream APIs
- Verified Rumble chat message sending via browser automation
- Clean startup synchronization with historical message cutoff
- Controlled send rate limiting
- Deterministic startup announcement
- Persistent browser sessions
- Clean Windows-safe shutdown behavior

This milestone establishes the foundation upon which all future features
and platforms will be built.

---

## Architecture Overview

StreamSuites is structured as a long-running asynchronous runtime,
orchestrated by a central scheduler and composed of platform-specific
workers.

High-level flow:

1. Application bootstraps environment and creator contexts
2. Scheduler launches per-creator runtimes
3. Platform workers manage platform-specific logic
4. Shared browser and job systems are centrally controlled
5. Clean shutdown propagates through all active tasks

---

## Repository Structure

```text
StreamSuites/
├── core/
│   ├── app.py              # Application entrypoint & lifecycle
│   ├── scheduler.py       # Task orchestration and shutdown control
│   ├── registry.py        # Creator loading and validation
│   ├── context.py         # Per-creator runtime context
│   └── jobs.py            # Job registry and dispatch
│
├── services/
│   └── rumble/
│       ├── browser/
│       │   └── browser_client.py   # Persistent Playwright browser control
│       └── workers/
│           ├── livestream_worker.py
│           └── chat_worker.py      # Chat read/write logic
│
├── shared/
│   ├── config/             # Static configuration (JSON)
│   ├── logging/            # Logging configuration
│   └── state/              # Runtime state (generated, gitignored)
│
├── media/
│   └── jobs/
│       └── clip_job.py     # Example job type
│
├── logs/                   # Runtime logs (gitignored)
├── .browser/               # Playwright persistent profile (gitignored)
├── .env.example
├── .gitignore
└── README.md
```
--- 

## Design Principles
- **Authoritative data sources**
Platform APIs are used where available; browser automation is used
only when required.

- **Single responsibility per component**
Browsers do browser things. Workers do platform things. The scheduler
controls lifecycle.

- **No hidden background state**
All long-running tasks are tracked and cancellable.

- **Windows-first compatibility**
Signal handling, shutdown, and event loops are designed to behave
correctly on Windows.

- **Configuration over code**
Behavior is being progressively externalized into JSON-based config.

---

## Roadmap (High-Level)
### Phase 1 — Core Stabilization (current)
- Rumble chat read/write
- Clean lifecycle
- Rate limiting
- Startup sync control

### Phase 2 — Configuration Externalization
- Chat behavior configuration (JSON)
- Rate limit configuration
- Trigger definitions

### Phase 3 — Dashboard Tooling
- HTML-based dashboard (GitHub Pages compatible)
- Creator configuration UI
- Job visibility and status
- Schema-driven validation

### Phase 4 — Multi-Platform Expansion
- Discord integration
- YouTube integration
- Twitch integration
- Shared user identity where feasible

### Phase 5 — Operator Tooling
- Windows desktop control application
- Runtime start/stop
- Configuration management
- Log inspection

---

## Notes
This repository intentionally prioritizes correctness and clarity over
rapid feature accumulation. All new functionality is expected to respect
the existing lifecycle and architectural boundaries.

---