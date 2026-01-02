# Pilled (Planned Ingest-Only)

Pilled integration is **planned** and remains ingest-only. No runtime workers
invoke these stubs, and no network traffic is produced. The files exist solely
to preserve architectural parity with other chat platforms and to keep the
scheduler wiring surface ready for future work.

## Scope
- Planned ingest-only; no outbound actions or chat sending.
- Placeholder API shims define the intended connection boundary.
- Kept separate from Kick to allow a lighter ingest-only client if the platform
  stabilizes.

## Files
- `api/chat.py` — Placeholder stub for future chat ingestion.
- `api/livestream.py` — Placeholder stub for future livestream metadata polling.
