# Operability Gates

## Current state

**Development usable: PASS. Internal testing ready: FAIL. External testing ready: FAIL. Real prospect ready: FAIL/not applicable to the current personal-tool boundary. Production ready: FAIL.**

The current operability estimate is **82%**. Core behavior, complete advanced editing and isolated Windows install/upgrade/restore/rollback acceptance pass. Rafael's real Desktop shortcut, retained-data check and human visual/accessibility acceptance remain missing.

Local Git, privacy exclusions and GitHub CI definitions are now present. These improve provenance but do not raise runtime readiness until the remote workflows actually pass.

## Development usable — PASS

- [x] Source starts on a clean temporary instance.
- [x] Schema initializes and copied database migrates with integrity `ok`.
- [x] Core timer, mission, project, AI exchange and backup logic have automated tests.
- [x] No unresolved P0 issue.
- [x] Project bootstrap and module contracts exist.

## Internal testing ready — FAIL

- [x] Development usable passes.
- [x] 54 Python tests pass on Linux and Windows.
- [x] Python/JavaScript/HTML static checks pass.
- [x] Multi-viewport Playwright workflow passes in actual Chromium.
- [x] All known P1 GUI discrepancies are closed or explicitly accepted.
- [x] Isolated Windows upgrade retains seeded data and creates a correctly targeted shortcut.
- [ ] Rafael's real Windows upgrade retains existing data and the Desktop shortcut launches it.

## External beta/testing ready — FAIL

- [ ] Internal testing ready passes.
- [x] Backup restoration drill passes in a disposable Windows target.
- [ ] Error messages and recovery are manually verified.
- [ ] Installation instructions are validated by a clean user path.
- [ ] Privacy boundaries and exported snapshot contents are reviewed.

## Real prospect ready — FAIL / currently outside product boundary

FORGE is a personal single-user tool, not a commercial product. If that boundary changes, this gate requires external-beta readiness, defined customer/support scope, licensing/privacy terms, safe distribution and at least one observed external-user workflow.

## Production ready — FAIL

- [ ] External testing ready passes.
- [ ] Repeatable release checklist and version provenance exist.
- [ ] Restore, rollback and upgrade procedures are executed successfully.
- [ ] UI accessibility acceptance passes.
- [ ] Observability supports diagnosis without exposing private journal data.
- [ ] No unresolved P0/P1 issue unless formally accepted with mitigation.
