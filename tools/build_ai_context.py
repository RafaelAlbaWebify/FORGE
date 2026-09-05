#!/usr/bin/env python3
"""Build deterministic FORGE AI bootstrap evidence without rewriting ledgers."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / ".ai"
GENERATED = AI / "generated"


def command(args: list[str]) -> dict:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"command": " ".join(args), "exit_code": result.returncode,
            "stdout": result.stdout[-8000:], "stderr": result.stderr[-4000:]}


def git_state() -> dict:
    probe = command(["git", "rev-parse", "--is-inside-work-tree"])
    if probe["exit_code"] != 0:
        return {"is_repository": False, "branch": None, "commit": None, "status": None}
    return {
        "is_repository": True,
        "branch": command(["git", "branch", "--show-current"])["stdout"].strip() or None,
        "commit": command(["git", "rev-parse", "HEAD"])["stdout"].strip() or None,
        "status": command(["git", "status", "--short"])["stdout"],
    }


def version() -> str | None:
    source = (ROOT / "forge_app.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION = "([^"]+)"', source, re.MULTILINE)
    return match.group(1) if match else None


def tree() -> list[str]:
    excluded = {"data", "backups", "exports", "build-dev", "__pycache__", ".git"}
    return [str(path.relative_to(ROOT)) for path in sorted(ROOT.rglob("*"))
            if path.is_file() and not any(part in excluded for part in path.relative_to(ROOT).parts)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    GENERATED.mkdir(parents=True, exist_ok=True)
    state = json.loads((AI / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    tests = command(["python", "-m", "unittest", "discover", "-s", "tests"]) if args.run_tests else None
    generated = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": "FORGE", "version": version(), "git": git_state(),
        "current_phase": state["current_phase"], "current_milestone": state["current_milestone"],
        "blockers": state["current_blockers"], "next_actions": state["next_recommended_actions"],
        "readiness": state["readiness"], "important_files": tree(), "test_run": tests,
        "notice": "Generated evidence only. Decisions, issues and historical ledgers remain manually maintained."
    }
    (GENERATED / "RUNTIME_STATE.json").write_text(json.dumps(generated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Generated FORGE Context", "", f"Generated: {generated['generated_at']}",
             f"Version: {generated['version']}", f"Git repository: {generated['git']['is_repository']}", "",
             f"Current milestone: {generated['current_milestone']}", "", "## Blockers", ""]
    lines += [f"- {item}" for item in generated["blockers"]]
    lines += ["", "## Next actions", ""] + [f"- {item}" for item in generated["next_actions"]]
    lines += ["", "## Test invocation", "", "Not requested." if tests is None else f"Exit code: {tests['exit_code']}"]
    (GENERATED / "AI_CONTEXT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(GENERATED / "RUNTIME_STATE.json")
    if tests and tests["exit_code"]:
        raise SystemExit(tests["exit_code"])


if __name__ == "__main__":
    main()
