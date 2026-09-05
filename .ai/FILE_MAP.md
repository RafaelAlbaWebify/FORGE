# Repository File Map

## Inspect first

1. `.ai/CONTEXT.md`
2. `.ai/PROJECT_STATE.json`
3. `.ai/KNOWN_ISSUES.md`
4. `.ai/OPERABILITY.md`
5. Contract relevant to the requested work under `.ai/contracts/`

## Runtime

- `forge_app.py` — application entrypoint, schema, domain logic, API and server.
- `static/index.html` — primary UI structure and dialogs.
- `static/app.js` — client state, rendering and interactions.
- `static/styles.css` — base visual system.
- `static/layout.css` — 0.9.1 layout/responsive corrections; consolidation pending.

## Installation and recovery

- `Install-FORGE.ps1` / `INSTALL_FORGE.bat` — Windows install/upgrade/rollback and Desktop shortcut.
- `Start-FORGE.ps1` / `START_FORGE.bat` — launch/reopen behavior.
- `Backup-FORGE.ps1` / `BACKUP_FORGE.bat` — verified backup entrypoints.

## Verification

- `tests/test_forge.py` — unit/integration/contract suite using disposable databases.
- `tests/ui_smoke.js` — Playwright daily/editor workflow and overflow checks, passing at four viewport sizes in GitHub Actions.
- `.ai/TEST_STATUS.json` — latest verified status.

## Generated/user-owned runtime data

- `data/forge.db` — development/sample database in this workspace; installed user database is authoritative for user records.
- `backups/` — generated SQLite backups; exclude from releases.
- `exports/` — generated AI snapshots/handoffs; exclude from releases.
- `build-dev/` — development artifact; exclude from releases.

## Project control

- `.ai/` — canonical AI bootstrap, roadmap, issues, decisions and gates.
- `tools/build_ai_context.py` — deterministic context/state builder.
- `README.md`, `VERSION.txt` — operator overview and release identity.
