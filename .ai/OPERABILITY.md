# Operability Gates

## Current state

**Personal single-user operability: PASS — 100%. Development usable: PASS. Internal testing ready: PASS. External distribution readiness: NOT REQUIRED for current scope.**

FORGE is fully operative for its intended boundary: Rafael's private, local, single-user Windows execution/evidence console. Core behavior, advanced editing, cross-platform CI, Windows install/upgrade/restore/rollback acceptance, Rafael's real-machine installation/database/runtime/browser acceptance, AI snapshot privacy, and manual recovery/error-message acceptance all pass.

The former 94% figure mixed personal operability with optional release/distribution hardening. Clean-user installation testing, repeatable public release provenance, frontend modularisation, legacy API cleanup and archive pagination are now tracked separately as distribution/maintainability work and do not reduce personal operability.

Local Git, privacy exclusions and GitHub CI are present. Runtime data remains local-only and outside Git. AI snapshots are explicitly treated as private, non-anonymised working data.

## Personal single-user operability — PASS (100%)

- [x] FORGE 0.10.0 is installed and runs from `%LOCALAPPDATA%\FORGE`.
- [x] Desktop shortcut targets the installed application correctly.
- [x] Existing personal records remain visible and SQLite integrity is `ok`.
- [x] Today, Map and Review workflows are human-accepted in the real browser.
- [x] Keyboard focus/navigation was human-accepted on the real machine.
- [x] Crash-safe timer, pause/resume and manual correction behavior are implemented and tested.
- [x] Verified backups, disposable restore, data-preserving upgrade and forced rollback pass.
- [x] A deliberately invalid upgrade produced a clear recovery message and restored the prior application/database.
- [x] AI snapshot export/import workflow and privacy boundary are reviewed and accepted for the current scope.
- [x] No unresolved P0/P1 issue blocks intended personal use.

## Development usable — PASS

- [x] Source starts on a clean temporary instance.
- [x] Schema initializes and copied database migrates with integrity `ok`.
- [x] Core timer, mission, project, AI exchange and backup logic have automated tests.
- [x] 54 Python tests pass on Linux and Windows.
- [x] Python/JavaScript/HTML static checks pass.
- [x] Multi-viewport Playwright workflow passes in actual Chromium.

## Optional external distribution readiness — not part of the 100% personal target

These items matter only if FORGE is distributed to other users or treated as a commercial/public product:

- [ ] Validate installation instructions on a genuinely clean external-user path.
- [ ] Formalise repeatable public release checklist and version provenance.
- [ ] Reassess privacy/support/licensing requirements for external users.

## Maintainability backlog — non-blocking

- [ ] Consolidate/split dense frontend source into bounded modules.
- [ ] Deprecate/remove unused legacy tomorrow-planning API paths.
- [ ] Add archive pagination only if dataset size approaches current caps.

If FORGE's product boundary changes beyond Rafael's personal single-user use, distribution and production readiness must be assessed independently rather than reducing the personal operability score.
