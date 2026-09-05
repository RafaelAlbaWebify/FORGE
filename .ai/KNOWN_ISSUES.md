# Known Issues

## FORGE-001 — Playwright UI run not evidenced

- Severity: P1
- Module: UI/testing
- Status: resolved 2026-09-05
- Description: the GitHub browser job now executes the daily workflow in real Chromium at four viewport sizes.
- Resolution evidence: Actions run 33947006546 passes at 1920×1080, 1366×768, 820×1000 and 390×844 after correcting the overflow-menu interaction.
- Follow-up: retain human Windows Chrome visual and accessibility acceptance as part of FORGE-003.

## FORGE-002 — Advanced editor lacks full field parity

- Severity: P1
- Module: UI
- Status: resolved 2026-09-05
- Description: backend supports more mission/project/milestone fields than the advanced dialog exposes. Examples include links, objective, milestone weight/evidence and several mission evidence/progress fields.
- Evidence: comparison of `normalize_*_fields` with `openEditor()`.
- Workaround: AI plan import or existing contextual outcome dialog for some fields.
- Blocking effect: earlier requirement that all sections be editable is not fully met through GUI.
- Resolution evidence: PR #1 exposes every retained user-owned field under compact Details sections; 52 tests and Playwright at four viewports passed in Actions run 33948072276.
- Follow-up: computed values and lifecycle state remain intentionally read-only or archive/restore-owned.

## FORGE-003 — Windows installer acceptance is stale/incomplete

- Severity: P1
- Module: packaging
- Status: open
- Description: automated 0.10.0 clean install, shortcut targeting, upgrade, restore and forced rollback pass on `windows-latest`; Rafael's real installation and Desktop shortcut still require human confirmation.
- Workaround: installer rollback and preserved-folder logic reduce risk.
- Blocking effect: production-ready gate remains closed.
- Next action: install the verified release on Rafael's PC, open it from the real Desktop shortcut and confirm existing records remain visible.

## FORGE-004 — Frontend maintainability debt

- Severity: P2
- Module: UI
- Status: open
- Description: `static/app.js` and `static/styles.css` are dense single files; `layout.css` is a corrective layer.
- Evidence: source inspection.
- Blocking effect: raises regression risk and slows review.
- Next action: split rendering, API, dialogs and views into bounded modules without changing runtime dependencies.

## FORGE-005 — Legacy tomorrow endpoints remain

- Severity: P2
- Module: core/API
- Status: open
- Description: `prepare_tomorrow` and `/api/tomorrow` remain even though the primary product decision moved planning to ChatGPT.
- Workaround: current UI does not call them.
- Blocking effect: creates two possible workflows and future ambiguity.
- Next action: deprecate with tests, then remove in a schema-compatible release if no export depends on it.

## FORGE-006 — Restore drill not verified

- Severity: P1
- Module: persistence/packaging
- Status: resolved 2026-09-05
- Description: backup creation and installer rollback paths have tests/code checks, but a complete operator-driven restore drill is not documented.
- Resolution evidence: Actions run 33949201547 copied a verified backup into a disposable restore target and confirmed SQLite integrity plus the seeded preservation marker.
- Follow-up: retain the operator-facing restore path in release acceptance.

## FORGE-007 — Archive listing is capped

- Severity: P3
- Module: API/UI
- Status: open
- Description: archive API returns at most 200 missions, 100 projects and 200 milestones without pagination.
- Workaround: sufficient for current small dataset.
- Next action: add pagination only when actual volume approaches the cap.

## FORGE-008 — Git source control unavailable

- Severity: P2
- Module: project control
- Status: resolved 2026-09-05
- Description: local Git history and the public `RafaelAlbaWebify/FORGE` remote now preserve application source and project-control history.
- Resolution evidence: baseline source published to GitHub with 43 tracked files; local runtime directories remain ignored.
- Follow-up: confirm all three hosted CI jobs pass before crediting readiness.
