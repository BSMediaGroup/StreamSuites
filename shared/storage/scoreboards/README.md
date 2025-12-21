# Scoreboard Export/Import Stubs

This directory scaffolds future scoreboard export/import flows. The runtime
remains authoritative for scoreboard data; these helpers will allow creators or
admins to move state between environments when implemented.

Scope (current):
- Define stub entry points for JSON/CSV import and export.
- Emphasize offline-safe, manual workflows.
- Avoid automation or background scheduling until rules are formalized.

Non-goals:
- No scoring calculations.
- No automatic triggers or periodic jobs.
- No file format enforcement beyond placeholders.
