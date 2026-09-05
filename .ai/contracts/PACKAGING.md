# Windows Packaging Contract

Responsibility: install or upgrade FORGE without losing user data and coexist with other local apps.

Inputs: extracted release ZIP and Python 3.10+. Outputs: `%LOCALAPPDATA%\FORGE`, Desktop shortcut and running verified version. Guarantees: preserve `data`, `exports`, `backups`; create pre-upgrade backup; stop only FORGE's process; validate version; rollback application/database on failed validation; search ports 8877–8896.

Release ZIP must exclude user databases, exports, backups, development builds and bytecode caches.

Acceptance command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-FORGE-Windows.ps1`. It uses a unique temporary installation and shortcut, verifies clean install, data-preserving upgrade, backup restore and forced rollback, then removes the sandbox. A final human check of the real Desktop shortcut remains required.
