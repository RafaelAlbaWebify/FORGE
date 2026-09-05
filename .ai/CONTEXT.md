# FORGE AI Bootstrap

FORGE is Rafael Alba's private, local Windows execution-and-evidence console. It records daily missions, outcome status, focused time, project/milestone evidence, study recall, blockers and decisions. Planning and prioritisation happen in ChatGPT; portable JSON snapshots and reviewed JSON plans are the controlled bridge.

## Boundaries

- Single-user and loopback-only; not a hosted collaboration/SaaS product.
- Times are guidance. Outcomes and evidence drive scores; timers do not award XP.
- JOLT and VERIDRA are separate applications. FORGE records their outcomes but does not control or monitor them.
- FORGE owns facts and history. ChatGPT owns sequencing, capacity decisions and tomorrow's plan.
- Imports must preserve evidence and measured time, reject stale plans and avoid duplicate operations.

## Runtime and components

- Python 3.10+ standard-library HTTP server: `forge_app.py`.
- SQLite/WAL persistence: installed `data/forge.db`.
- Dependency-free HTML/CSS/JavaScript UI: `static/`.
- PowerShell Windows install/start/backup scripts at repository root.
- Tests: `tests/test_forge.py`; Playwright smoke specification: `tests/ui_smoke.js`.

## Current verified state

- Version: 0.10.0.
- 52 Python tests pass on Linux and Windows on 2026-09-05.
- Python/JavaScript syntax, HTML structure, clean-server API and copied-database migration checks pass.
- Playwright passes the daily and advanced-editor workflow in hosted Chromium at four supported viewport sizes.
- Current milestone: execute the 0.10.0 installer/upgrade and backup-restore acceptance on a real Windows machine.

## Start here

1. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md` and `.ai/OPERABILITY.md`.
2. Inspect working-tree and remote state. The canonical branch is `main` and the public GitHub remote is `RafaelAlbaWebify/FORGE`; do not invent commit or CI status.
3. Read the relevant contract in `.ai/contracts/` and only then inspect its implementation.
4. Run `python tools/build_ai_context.py --run-tests` when Python is available.
5. Update canonical `.ai/` state before ending material work.

Authoritative deeper files: `README.md`, `forge_app.py`, `static/`, `tests/`, `Install-FORGE.ps1`, and the remaining `.ai/` documents.
