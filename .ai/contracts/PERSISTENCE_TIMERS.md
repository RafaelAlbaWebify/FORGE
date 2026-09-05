# Persistence and Timer Contract

Responsibility: preserve missions/projects/evidence and measure explicit human focus.

Inputs: validated domain fields, timer actions and manual corrections. Outputs: SQLite records and computed elapsed time. Guarantees: WAL/foreign keys; one human focus timer; system timestamps; pause/resume accumulation; corrections are separate auditable records; completed/deferred work cannot start; crash recovery stops at the last heartbeat; archive preserves history.

Dependencies: SQLite and writable `data/`. Failures must not silently reset data or infer hours from next launch time.

Non-responsibilities: passive activity tracking, JOLT/VERIDRA runtime tracking, automatic productivity judgment or deleting archived history.
