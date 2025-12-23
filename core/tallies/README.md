# Tallies (runtime concept, schema-only)

Tallies are a first-class runtime concept that track categorical counts without
sharing state or logic with polls, clips, or votes.

## Scope

- Defines serializable tally shapes (`Tally`, `TallyCategory`, `TallyOption`)
  for runtime awareness and future exports.
- Captures aggregation intent (`weekly`, `monthly`, `rolling`, `custom`) while
  deferring scheduling, triggers, and live aggregation.
- Keeps tally data isolated from poll mechanics and voting flows.

## Future readiness

- Dashboard and public gallery/detail views can consume the schema via
  read-only snapshots without requiring runtime mutations.
- Exporters can produce snapshot documents using `Tally.to_document()` when
  ready, keeping parity with poll exports but without mixing storage.

No execution logic lives in this package yet; only schema and serialization
helpers are provided.
