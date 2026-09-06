# AI Exchange Contract

Responsibility: export portable evidence and safely import reviewed planning decisions.

Snapshot output: `forge-snapshot` schema 2.0 with current work, bounded history, projects, blockers, study data, constraints, embedded ChatGPT instructions and return contract.

## Privacy boundary

The snapshot is **portable but not anonymised**. It intentionally contains user-entered planning evidence needed for useful external analysis, including mission titles/results/next actions, blockers, project and milestone evidence, daily reflection when present, study recall and recorded planning decisions. Treat the generated JSON as private working data and review it before uploading or sharing it outside the intended planning chat.

The export is structurally bounded: detailed history is limited to fourteen days and older history is reduced to monthly aggregates. It does not export the SQLite database, backup files, export-directory contents, application installation/root paths, server identity, raw timer-session records or raw timer start/stop timestamps. Stable record IDs and selected record timestamps may accompany planning records because stale-plan protection depends on local update ordering.

Free-text fields can contain whatever the user typed into FORGE; FORGE cannot guarantee that those fields are free of names, employer/client details, URLs, credentials or other sensitive information. Secrets should never be stored in FORGE, and snapshots should not be treated as sanitised exports.

Plan input: `forge-ai-plan` 1.0/2.0 with no more than 100 validated operations. Guarantees: stable existing IDs; latest-export binding; updated-at stale checks; operation ledger idempotency; backup before mutation; milestone regressions default to manual review; selected operations only.

Failure behavior: reject unknown protocol/actions/IDs/fields, invalid bounds, stale exports and repeated operations. Never alter raw measured timer sessions through AI import.

Non-responsibilities: calling ChatGPT directly, silently planning tomorrow, sanitising arbitrary user-entered free text, or trusting AI text as evidence without user review.
