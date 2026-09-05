# Core Runtime Contract

Responsibility: start one local FORGE instance, select a safe loopback port, expose bounded HTTP endpoints and coordinate domain operations.

Inputs: CLI host/port options and validated local JSON requests. Outputs: JSON responses, static assets and explicit downloads. Guarantees: loopback default; second launch reopens existing FORGE; bounded request size; errors return 4xx JSON where handled.

Dependencies: Python 3.10+ standard library, persistence contract and static files. Failure behavior: refuse startup if no port is available; never migrate/reconcile merely because a second shortcut was clicked.

Non-responsibilities: cloud hosting, authentication for network clients, multi-user concurrency and external project process control.
