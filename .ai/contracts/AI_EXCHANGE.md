# AI Exchange Contract

Responsibility: export portable evidence and safely import reviewed planning decisions.

Snapshot output: `forge-snapshot` schema 2.0 with current work, bounded history, projects, blockers, study data, constraints, embedded ChatGPT instructions and return contract.

Plan input: `forge-ai-plan` 1.0/2.0 with no more than 100 validated operations. Guarantees: stable existing IDs; latest-export binding; updated-at stale checks; operation ledger idempotency; backup before mutation; milestone regressions default to manual review; selected operations only.

Failure behavior: reject unknown protocol/actions/IDs/fields, invalid bounds, stale exports and repeated operations. Never alter raw measured timer sessions through AI import.

Non-responsibilities: calling ChatGPT directly, silently planning tomorrow or trusting AI text as evidence without user review.
