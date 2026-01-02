# Trigger Pipelines (Conceptual)

This directory houses trigger scaffolding for chat/runtime signals. Triggers
remain pure detection logic with no side effects. Execution and scoring are
separate concerns.

## Trigger Pipelines
- Triggers are composed into pipelines that receive chat or platform events.
- Each trigger decides whether it matches and emits an **action descriptor**.
- Downstream components interpret descriptors; triggers do not execute actions.

## Score Events (Foundational)
- Some triggers will emit `score` actions to feed scoreboard modules.
- Detection is decoupled from scoring: triggers surface events, scoreboards own
  aggregation.
- No scoring math exists here; emitted payloads remain placeholders until
  scoreboard logic is defined.

## Separation of Concerns
- Detection (here): pattern/heuristic matching only.
- Scoring (elsewhere): scoreboard registry + future math.
- Storage: runtime/state publishers remain the source of truth; dashboards read
  published snapshots.

## Validation trigger (smoke test)
- `NonEmptyChatValidationTrigger` fires on any non-empty chat message and emits
  a `validation_passed` action descriptor. This keeps trigger → action →
  exporter wiring observable even while chat pipelines are stubbed.
