# Generated FORGE Context

Generated: 2026-09-05T04:41:47+00:00
Version: 0.10.0
Git repository: True

Current milestone: Verify the 0.10.0 daily workflow in Windows Chrome and close remaining P1 GUI gaps

## Blockers

- Playwright browser smoke suite has not completed in the current environment
- Fresh 0.10.0 Windows install/upgrade and visual acceptance are not yet evidenced
- Advanced GUI editing does not expose every backend-supported field

## Next actions

- Connect a private GitHub remote and verify the core, browser and Windows-runtime CI jobs
- Run tests/ui_smoke.js against installed FORGE on Windows with Playwright available
- Capture screenshots at 1920x1080, 1366x768 and narrow widths and record defects
- Expose or intentionally remove every backend-editable field from the advanced GUI
- Perform and document a backup-to-restore drill
- Only then reassess internal-testing readiness

## Test invocation

Exit code: 0
