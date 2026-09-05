# Recommended Chat / Workstream Structure

Use four persistent workstreams; more would fragment a small codebase.

1. **Core / Integration** — architecture, roadmap, releases, readiness gates, cross-module changes and AI protocol policy.
2. **Runtime / Data** — SQLite, migrations, timers, scoring, backups, recovery and API domain logic.
3. **UI / Workflow** — Today/Map/Review, dialogs, responsive/accessibility work and Playwright acceptance.
4. **Windows / Release** — installer, shortcut, port coexistence, upgrade/rollback drills and packaging.

Each chat begins with `.ai/CONTEXT.md` and the canonical state, then loads only its contract and relevant source. Cross-workstream communication occurs by updating `.ai/`, tests and repository evidence—not by assuming another chat's memory.
