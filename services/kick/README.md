# Kick Chatbot (Scaffold)

This directory mirrors the Twitch/YouTube platform layout while remaining
stubbed for early validation. The goal is to keep deterministic interfaces so
workers can be wired into the scheduler later without refactoring.

## Scope (alpha scaffold)
- No live network calls are issued.
- Auth handshake is stubbed and returns a placeholder token structure.
- Chat connection is simulated; workers emit normalized chat events for trigger
  evaluation without sending traffic to Kick.
- Message normalization matches existing trigger contracts and records
  `runtime_state` heartbeats.

## Environment (already present)
- `KICK_CLIENT_ID_DANIEL`
- `KICK_CLIENT_SECRET`
- `KICK_USERNAME_DANIEL`
- `KICK_BOT_NAME`
- `KICK_STREAMKEY_DANIEL`

Secrets are **never** logged. The stub only checks presence to prove that
credentials are plumbed into the runtime environment.

## Files
- `api/chat.py` — Auth and connection stubs that yield normalized messages.
- `models/message.py` — Normalized chat message shape with `to_event()` helper.
- `workers/chat_worker.py` — Scheduler-owned stub worker that exercises
  heartbeat, trigger validation, and action execution hooks.
- `workers/livestream_worker.py` — Placeholder livestream worker documenting the
  future ingest path.

## Future wiring
- Replace stubbed auth/token exchange with Kick OAuth or session bootstrap.
- Swap the simulated iterator for a WebSocket/HTTP SSE client.
- Register platform in `core/scheduler` once Kick endpoints are proven stable
  and deterministic.
