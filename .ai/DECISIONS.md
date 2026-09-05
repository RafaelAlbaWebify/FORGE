# Durable Decisions

## D-001 — Local-first single-user application

- Status: accepted
- Decision: bind only to loopback and store data locally in SQLite.
- Reason: privacy, simplicity and coexistence with local tools.
- Consequence: no remote access, collaboration or cloud synchronisation.

## D-002 — Planning belongs outside FORGE

- Status: accepted
- Decision: ChatGPT plans and prioritises; FORGE executes and records evidence.
- Alternatives: in-app scheduling and automatic tomorrow generation.
- Consequence: JSON exchange must be portable, safe and self-describing.

## D-003 — Milestones over rigid timetables

- Status: accepted
- Decision: proposed time is guidance; completion and evidence determine progress.
- Reason: Rafael's energy varies and afternoon concentration is lower.

## D-004 — One human timer at a time

- Status: accepted
- Decision: starting a focus timer pauses any other running focus timer.
- Consequence: JOLT/VERIDRA can run independently in parallel, but background automation is not counted as human focus.

## D-005 — No passive surveillance

- Status: accepted
- Decision: collect only explicit timer sessions and user-entered evidence.
- Alternative: RescueTime-style desktop monitoring.

## D-006 — Reversible mutation and preserved history

- Status: accepted
- Decision: archive instead of hard-delete; backup before migrations/imports; preserve installed data during upgrades.

## D-007 — Conservative AI progress

- Status: accepted
- Decision: imported milestone estimates carry evidence confidence and regressions require review.

## D-008 — Compact primary UI

- Status: accepted
- Decision: Today, Map and Review are primary; structure editing, archive and backup sit under the overflow menu.

## D-009 — Dual local-data/public-code model

- Status: accepted
- Decision: the local installation is authoritative for personal runtime data; Git and the public GitHub repository are authoritative for source, tests, documentation and release automation.
- Reason: preserve private journal data while gaining reviewable history, rollback, CI and off-device source continuity.
- Consequence: `data/`, `backups/`, `exports/`, secrets and generated local artifacts are ignored and must never enter commits or release packages. Public visibility is accepted so standard GitHub-hosted Actions do not consume the private-repository allowance.

## D-010 — Minimal branch workflow

- Status: accepted
- Decision: use protected `main` plus short-lived `feature/*` and `fix/*` branches; do not maintain a permanent `develop` branch.
- Reason: FORGE is a single-user application and does not benefit from additional branch ceremony.
