# FORGE 0.10.0

FORGE is a private local execution and evidence console. FORGE records facts; ChatGPT analyses, prioritises and returns the next plan through portable JSON files.

Future development sessions bootstrap from `.ai/CONTEXT.md` and `.ai/PROJECT_STATE.json`; repository evidence is authoritative over chat history.

## Local data + public GitHub model

- **The computer is authoritative for personal runtime data:** `data/`, `backups/` and `exports/` never enter Git.
- **Git is authoritative for reproducible project assets:** source, tests, Windows scripts, documentation and `.ai/` control files.
- **The public GitHub repository provides off-device source history and unrestricted standard-runner CI.** It contains application code only; it is not a journal sync service.
- Work on short-lived `feature/*` or `fix/*` branches, verify through a pull request, then merge to `main`. Keep the model deliberately small; no permanent `develop` branch.

Run `python tools/build_release.py --output dist/FORGE_WINDOWS.zip` to create a privacy-checked Windows package. GitHub Actions repeats the unit, browser, Windows-runtime and packaging checks.

## Install or upgrade on Windows

1. Extract the ZIP.
2. Double-click `INSTALL_FORGE.bat`.
3. Open FORGE from the automatic Desktop shortcut.

The installer stops only the prior FORGE process, creates a verified backup, preserves the database/exports/backups, applies additive migrations, verifies version 0.10.0, and restores the previous application and database if validation fails. JOLT and VERIDRA can run simultaneously because FORGE selects the first free loopback port from `127.0.0.1:8877–8896`.

For an isolated Windows acceptance test that does not alter the real installation, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-FORGE-Windows.ps1`. It checks installation, shortcut targeting, data-preserving upgrade, backup restoration and forced rollback inside a disposable `%TEMP%` folder.

## Minimal daily workflow

1. Work from **NOW**, with at most two human-focus actions in **NEXT**. JOLT and VERIDRA remain compact in **BACKGROUND**.
2. Use **Start**, **Pause**, and **Finish**. Closing FORGE cannot erase measured work; interrupted sessions reopen paused at the last heartbeat.
3. On Finish, record one short result and tap Not started, Advanced, Completed, or Blocked. Blocker, evidence, next action, and study recall are contextual or optional.
4. Select **AI snapshot**, review the JSON if needed, upload it to the FORGE planning chat, and import the returned AI plan.
5. Review the visual before/after changes and apply selected or all safe changes.

## AI snapshot

The self-contained snapshot includes embedded instructions and the exact return schema, current work and evidence, fourteen detailed days, compact older aggregates, planning constraints, study reviews and planning decisions. Stable IDs and timestamps protect imports against stale or repeated changes.

The snapshot is **private working data, not an anonymised export**. User-entered results, blockers, reflections, project evidence, study recall and planning decisions may appear verbatim. It excludes the database and backup files, installation paths, server identity and raw timer-session records/timestamps, but free-text fields can still contain sensitive information the user entered. Review a snapshot before sharing it outside the intended planning chat and never store credentials or secrets in FORGE.

## Views

- **Today:** NOW, NEXT, BACKGROUND and LATER.
- **Map:** project and milestone bars with confidence and next actions.
- **Review:** weekly outcomes, planned versus actual effort, project progress, time-of-day performance, aging blockers and decisions.

Timers never award XP; validated outcomes do. Sustainability is separate from professional XP.

## Data

- Database: `data\forge.db`
- AI snapshots: `exports\`
- Verified backups: `backups\`
- Network: loopback only (`127.0.0.1`)

No cloud account, API key or extra Python package is required. Python 3.10+ must be available.
