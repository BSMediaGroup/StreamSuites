# Kick Chatbot (Scaffold)

This directory mirrors the Twitch/YouTube platform layout with a runnable
offline scaffold. Credentials are validated, chat messages are normalized, and
triggers fire through the scheduler without hitting Kick network endpoints.

## Scope (alpha scaffold)
- No live network calls are issued (offline scaffold).
- Auth handshake validates env presence and provisions a deterministic session
  token.
- Chat connection uses a buffered poll loop; workers emit normalized chat
  events for trigger evaluation without sending traffic to Kick.
- Message normalization matches existing trigger contracts and records
  `runtime_state` heartbeats and counters.

## Environment (already present)
- `KICK_CLIENT_ID_*` (e.g., `KICK_CLIENT_ID_DANIEL`)
- `KICK_CLIENT_SECRET_*` (e.g., `KICK_CLIENT_SECRET_DANIEL`)
- `KICK_USERNAME_*` (creator-specific handle) or `KICK_BOT_NAME`
- `KICK_STREAMKEY_*` (reserved for livestream control)

Secrets are **never** logged. The stub only checks presence to prove that
credentials are plumbed into the runtime environment.

## Files
- `api/chat.py` — Auth + pollable chat client with env validation and
  normalized messages.
- `models/message.py` — Normalized chat message shape with `to_event()` helper.
- `workers/chat_worker.py` — Scheduler-owned stub worker that exercises
  heartbeat, trigger validation, and action execution hooks.
- `workers/livestream_worker.py` — Placeholder livestream worker documenting the
  future ingest path.

## Future wiring
- Replace stubbed auth/token exchange with Kick OAuth or session bootstrap.
- Swap the simulated iterator for a WebSocket/HTTP SSE client.
- Keep feature-flagged scheduler wiring aligned with `kick.enabled` before
  enabling live sockets.
