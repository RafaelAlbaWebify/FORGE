# AI Session Protocol

## Start

1. Read `CONTEXT.md`, `PROJECT_STATE.json`, `KNOWN_ISSUES.md` and `OPERABILITY.md` completely.
2. Check Git status and commit. If the directory is not Git-backed, record that fact; never invent identifiers.
3. Read the relevant contract under `contracts/`.
4. Load only source/tests needed for the active objective.
5. Verify claims against runtime tests and current source before editing.

## During work

- Keep the change bounded and preserve documented contracts.
- Protect user data and preserve additive migrations.
- Add or update tests for behavior changes.
- Distinguish implementation, static validation, API validation, browser validation and Windows validation.
- Record new issues and durable decisions as they arise.
- Do not declare readiness from code presence alone.

## End

Update, when affected: `PROJECT_STATE.json`, `TEST_STATUS.json`, `KNOWN_ISSUES.md`, `ROADMAP.md`, `DECISIONS.md`, `REJECTED_APPROACHES.md`, and `OPERABILITY.md`.

Record what changed, exact verification performed, failures/skips, remaining work, Git state and the next bounded action. Run `python tools/build_ai_context.py --run-tests` to refresh deterministic generated context. A new chat must bootstrap from `.ai/`, not from “review the previous chat.”

## Evidence hierarchy

1. Current executed runtime/test evidence.
2. Current source.
3. Current configuration/data.
4. Canonical `.ai/` and operator documentation.
5. Older documentation/chat.
6. Explicitly labelled assumptions.
