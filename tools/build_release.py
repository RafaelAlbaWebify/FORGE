#!/usr/bin/env python3
"""Build a deterministic, privacy-safe FORGE Windows release ZIP."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git", ".github", ".ai", "data", "backups", "exports", "build-dev",
    "__pycache__", "node_modules", "dist", "test-results", "playwright-report",
}
EXCLUDED_SUFFIXES = {".db", ".db-wal", ".db-shm", ".pyc", ".zip", ".log"}
RELEASE_ROOT_FILES = {
    "forge_app.py", "README.md", "VERSION.txt", "INSTALL_FORGE.bat",
    "Install-FORGE.ps1", "START_FORGE.bat", "Start-FORGE.ps1",
    "BACKUP_FORGE.bat", "Backup-FORGE.ps1",
}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return relative.parts[0] == "static" or str(relative) in RELEASE_ROOT_FILES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in sorted(ROOT.rglob("*")) if path.is_file() and included(path)]
    if not files:
        raise SystemExit("No release files selected")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, Path("FORGE") / path.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        unsafe = [name for name in archive.namelist() if any(
            token in name.lower() for token in ("forge.db", "/data/", "/backups/", "/exports/", ".env")
        )]
        if unsafe:
            output.unlink(missing_ok=True)
            raise SystemExit(f"Private files entered release: {unsafe}")
    print(output)


if __name__ == "__main__":
    main()
