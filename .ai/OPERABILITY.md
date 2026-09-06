# Operability Gates

## Current state

**Development usable: PASS. Internal testing ready: PASS. External testing ready: FAIL. Real prospect ready: FAIL/not applicable to the current personal-tool boundary. Production ready: FAIL.**

The current operability estimate is **94%**. Core behavior, complete advanced editing, cross-platform CI, automated Windows install/upgrade/restore/rollback acceptance, Rafael's real-machine installation/database/runtime/browser acceptance, the AI snapshot privacy boundary, and manual recovery/error-message acceptance all pass. The remaining external-testing gate is clean-user installation instruction validation. Production hardening still requires release provenance and the other production gates below.

Local Git, privacy exclusions and GitHub CI are present. Runtime data remains local-only and outside Git. AI snapshots are explicitly treated as private, non-anonymised working data.

## Development usable — PASS

- [x] Source starts on a clean temporary instance.
- [x] Schema initializes and copied database migrates with integrity `ok`.
- [x] Core timer, mission, project, AI exchange and backup logic have automated tests.
- [x] No unresolved P0 issue.
- [x] Project bootstrap and module contracts exist.

## Internal testing ready — PASS

- [x] Development usable passes.
- [x] 54 Python tests pass on Linux and Windows.
- [x] Python/JavaScript/HTML static checks pass.
- [x] Multi-viewport Playwright workflow passes in actual Chromium.
- [x] All known P1 GUI discrepancies are closed or explicitly accepted.
- [x] Isolated Windows upgrade retains seeded data and creates a correctly targeted shortcut.
- [x] Rafael's real installation is FORGE 0.10.0 at `%LOCALAPPDATA%\FORGE`; the Desktop shortcut targets the installed `forge_app.py`.
- [x] Rafael's real `forge.db` reports SQLite integrity `ok` with 100 missions, 22 timer sessions, 19 time adjustments, 6 projects, 30 milestones and 0 daily notes.
- [x] A running real-machine instance reports app `FORGE`, version `0.10.0`, and root `C:\Users\ralba\AppData\Local\FORGE` through `/api/identity`.
- [x] Rafael confirmed retained data is visible and Today, Map, Review and keyboard focus all look correct in the real browser.

## External beta/testing ready — FAIL

- [x] Internal testing ready passes.
- [x] Backup restoration drill passes in a disposable Windows target.
- [x] Error messages and recovery are manually verified: on 2026-09-06 a deliberately invalid upgrade reported `Upgrade failed; the previous FORGE version and database were restored.`, preserved the seeded database marker, restored the prior 0.10.0 application, and the isolated harness ended `[5/5] PASS - install, shortcut, upgrade, backup/restore and rollback`.
- [ ] Installation instructions are validated by a clean user path.
- [x] Privacy boundaries and exported snapshot contents are reviewed and accepted for the current single-user scope: detailed history is bounded to fourteen days, older history is aggregated, raw database/backups/install paths/server identity/raw timer-session records are excluded, and user-entered free text is explicitly documented as private and non-anonymised.

## Real prospect ready — FAIL / currently outside product boundary

FORGE is a personal single-user tool, not a commercial product. If that boundary changes, this gate requires external-beta readiness, defined customer/support scope, licensing/privacy terms, safe distribution and at least one observed external-user workflow.

## Production ready — FAIL

- [ ] External testing ready passes.
- [ ] Repeatable release checklist and version provenance exist.
- [ ] Restore, rollback and upgrade procedures are executed successfully on the intended release path.
- [ ] UI accessibility acceptance passes.
- [ ] Observability supports diagnosis without exposing private journal data.
- [ ] No unresolved P0/P1 issue unless formally accepted with mitigation.
