# Runtime changelog format (authoritative)

`changelog.runtime.json` in this directory defines the canonical JSON shape for runtime-scoped changelog entries consumed by StreamSuites surfaces.

- The format is **authoritative for structure** only; it may be edited manually or updated by CI when available.
- Entries must include `id`, `date`, `title`, `description`, `scope` (always `"runtime"`), and `version`.
- No dashboard-specific or UI-only fields are permitted here.

## Export expectations

- Any export or formatter should **only write JSON** that matches this structure. It must not attempt to watch files, run at runtime startup, or assume a GitHub Pages target.
- Changelog export is **manual or CI-driven**; there is **no runtime-driven emission** and no background writers are allowed.
- This file is intended to be copied or synced into `StreamSuites-Dashboard/docs/data/` when publishing updates.
- Future GitHub Actions may automate the copy/sync step, but **no automation exists yet**.
