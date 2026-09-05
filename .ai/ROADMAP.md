# FORGE Roadmap

Status requires acceptance evidence, not code presence.

| ID | State | Work | Dependencies | Acceptance criteria | Evidence |
|---|---|---|---|---|---|
| F-001 | Completed | Reliable focus timers | SQLite | Start/pause/resume/finish accumulate; restart recovery and correction work | Python timer tests |
| F-002 | Completed | AI snapshot/import v2 | Stable IDs, SQLite | Self-describing export; stale and duplicate imports rejected; preview selectable | Export/import tests |
| F-003 | Completed | Compact Today/Map/Review structure | API payloads | Three views render from current APIs; no old v080 assets | Frontend contract tests |
| F-004 | Active | Windows GUI acceptance | 0.10.0 installed; browser | No overlap/overflow; every primary action works at target viewports | Executed Playwright report + screenshots |
| F-005 | Completed | Advanced editor parity | Field inventory | Every retained user-owned field is editable or explicitly AI-owned/read-only | 52 tests + Actions run 33948072276 |
| F-006 | Completed | Backup restoration drill | Valid backup | Restore copy boots with unchanged counts and integrity check | Actions run 33949201547 |
| F-007 | Next | Frontend consolidation | F-004/F-005 | Maintainable modules; no corrective CSS layering; behavior unchanged | Review + UI regression suite |
| F-008 | Active | Installer acceptance | Windows + prior DB | Upgrade retains record counts, shortcut works, rollback simulated | Automated pass; Rafael's PC pending |
| F-009 | Later | Accessibility pass | Stable UI | Keyboard navigation, names, contrast and focus pass agreed checks | Axe/manual evidence |
| F-010 | Later | Release diagnostics | Stable runtime | User can export safe diagnostics without private journal content | Redacted diagnostic artifact test |
| F-011 | Optional | Signed/packaged runtime | Distribution decision | Works without separate Python installation | Clean Windows VM evidence |
| F-012 | Rejected | In-app automatic planning | None | Out of scope: ChatGPT remains planner | Decision D-002 |
| F-013 | Rejected | Passive desktop surveillance | None | Out of scope: only user-started timers | Decision D-005 |
