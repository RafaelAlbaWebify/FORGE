#!/usr/bin/env python3
"""FORGE: local milestone-driven daily journal and project orchestrator."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import shutil
import sqlite3
import threading
import uuid
import webbrowser
import zipfile
from datetime import date, datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

APP_VERSION = "0.10.0"
VALID_STATUSES = {"not_started", "advanced", "completed", "blocked", "deferred"}
VALID_PRIORITIES = {"keystone", "important", "parallel", "support", "close"}
MAX_TEXT = 10_000
HEARTBEAT_SECONDS = 5
TIMER_LOCK = threading.Lock()

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB_PATH = DATA / "forge.db"
STATIC = ROOT / "static"
EXPORTS = ROOT / "exports"
BACKUPS = ROOT / "backups"

AREAS = {
    "study": ("📚", "Professional study", "#8b5cf6"),
    "employment": ("💼", "Employment", "#2563eb"),
    "interview": ("🎤", "Interview readiness", "#06b6d4"),
    "recovery": ("❤️", "Recovery", "#ec4899"),
    "webify": ("🏢", "Webify", "#f59e0b"),
    "youtube": ("🎬", "YouTube", "#ef4444"),
    "jolt": ("🛠️", "JOLT", "#14b8a6"),
    "veridra": ("🔍", "VERIDRA", "#22c55e"),
    "orchestration": ("🧭", "Orchestration", "#6366f1"),
    "life": ("🌿", "Life & sustainability", "#10b981"),
}

DEFAULT_MISSIONS = [
    ("study", "Complete the next Azure & Intune practical milestone", "keystone", "Morning", 45, 10, 10),
    ("employment", "Complete 1–3 strong employment actions", "keystone", "Morning", 135, 25, 20),
    ("interview", "Practise one relevant subject and 3–5 answers aloud", "important", "Late morning", 45, 10, 30),
    ("recovery", "Lunch and genuine disconnection", "support", "Midday", 90, 5, 40),
    ("webify", "Complete the current commercial dependency", "important", "Early afternoon", 60, 15, 50),
    ("youtube", "Validate the current production milestone", "important", "Afternoon", 90, 15, 60),
    ("jolt", "Advance one bounded validated task", "parallel", "Anytime", 30, 5, 70),
    ("veridra", "Advance one bounded commercial task", "parallel", "Anytime", 30, 5, 80),
    ("orchestration", "Record results and define tomorrow’s exact first actions", "close", "End of day", 15, 5, 90),
    ("life", "Close work and fully disconnect", "close", "After work", 0, 5, 100),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def init_db() -> None:
    for folder in (DATA, EXPORTS, BACKUPS):
        folder.mkdir(exist_ok=True)
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS missions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              day TEXT NOT NULL, area TEXT NOT NULL, title TEXT NOT NULL,
              priority TEXT NOT NULL DEFAULT 'important', best_time TEXT DEFAULT '',
              suggested_minutes INTEGER NOT NULL DEFAULT 30,
              status TEXT NOT NULL DEFAULT 'not_started', result TEXT DEFAULT '',
              next_action TEXT DEFAULT '', progress_before REAL DEFAULT 0,
              progress_after REAL DEFAULT 0, score_weight REAL NOT NULL DEFAULT 0,
              timer_state TEXT NOT NULL DEFAULT 'idle',
              project_id INTEGER, milestone_id INTEGER,
              success_evidence TEXT DEFAULT '', resume_location TEXT DEFAULT '',
              blocker_reason TEXT DEFAULT '', blocker_active INTEGER NOT NULL DEFAULT 0, if_then_cue TEXT DEFAULT '',
              rollover_from_id INTEGER,
              active INTEGER NOT NULL DEFAULT 1,
              sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS timer_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER NOT NULL,
              mode TEXT NOT NULL DEFAULT 'focus', started_at TEXT NOT NULL,
              stopped_at TEXT, elapsed_seconds INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS time_adjustments (
              id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER NOT NULL,
              adjustment_seconds INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT 'manual correction',
              created_at TEXT NOT NULL,
              FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS projects (
              id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
              area TEXT NOT NULL, objective TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
              next_action TEXT DEFAULT '', updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS milestones (
              id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
              title TEXT NOT NULL, weight REAL NOT NULL, progress REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'not_started', evidence TEXT DEFAULT '',
              sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS daily_notes (
              day TEXT PRIMARY KEY, energy_start INTEGER, energy_end INTEGER,
              reflection TEXT DEFAULT '', tomorrow_focus TEXT DEFAULT '', updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_meta (
              key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_import_operations (
              plan_key TEXT NOT NULL, operation_id TEXT NOT NULL,
              action TEXT NOT NULL, applied_at TEXT NOT NULL,
              PRIMARY KEY(plan_key, operation_id)
            );
            CREATE TABLE IF NOT EXISTS planning_decisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL,
              decision TEXT NOT NULL, reason TEXT DEFAULT '', source TEXT NOT NULL DEFAULT 'chatgpt',
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS study_reviews (
              id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER NOT NULL UNIQUE,
              recall TEXT, practice TEXT, next_review_day TEXT, updated_at TEXT NOT NULL,
              FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
            );
            """
        )
        columns = {row[1] for row in con.execute("PRAGMA table_info(missions)")}
        if "timer_state" not in columns:
            con.execute("ALTER TABLE missions ADD COLUMN timer_state TEXT NOT NULL DEFAULT 'idle'")
            con.execute("UPDATE missions SET timer_state='paused' WHERE id IN (SELECT DISTINCT mission_id FROM timer_sessions)")
            con.execute("UPDATE missions SET timer_state='running' WHERE id IN (SELECT DISTINCT mission_id FROM timer_sessions WHERE stopped_at IS NULL AND mode='focus')")
        if "active" not in columns:
            con.execute("ALTER TABLE missions ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        mission_migrations = {
            "project_id": "INTEGER", "milestone_id": "INTEGER",
            "success_evidence": "TEXT DEFAULT ''", "resume_location": "TEXT DEFAULT ''",
            "blocker_reason": "TEXT DEFAULT ''", "blocker_active": "INTEGER NOT NULL DEFAULT 0", "if_then_cue": "TEXT DEFAULT ''",
            "rollover_from_id": "INTEGER",
        }
        for column, definition in mission_migrations.items():
            if column not in columns:
                con.execute(f"ALTER TABLE missions ADD COLUMN {column} {definition}")
        con.execute("UPDATE missions SET blocker_active=1 WHERE blocker_reason!='' AND status!='completed' AND blocker_active=0")
        milestone_columns = {row[1] for row in con.execute("PRAGMA table_info(milestones)")}
        if "active" not in milestone_columns:
            con.execute("ALTER TABLE milestones ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        if "updated_at" not in milestone_columns:
            con.execute("ALTER TABLE milestones ADD COLUMN updated_at TEXT")
            con.execute("UPDATE milestones SET updated_at=? WHERE updated_at IS NULL", (now_iso(),))
        for column, definition in {
            "confidence": "TEXT NOT NULL DEFAULT 'low'",
            "completion_conditions": "TEXT DEFAULT ''",
        }.items():
            if column not in milestone_columns:
                con.execute(f"ALTER TABLE milestones ADD COLUMN {column} {definition}")
        project_columns = {row[1] for row in con.execute("PRAGMA table_info(projects)")}
        if "priority_rank" not in project_columns:
            con.execute("ALTER TABLE projects ADD COLUMN priority_rank INTEGER NOT NULL DEFAULT 999")
        if con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            seed_projects(con)
        link_unlinked_missions(con)
    ensure_day(date.today().isoformat())


def automatic_daily_backup() -> Path:
    """Create at most one verified database backup per local calendar day."""
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"forge_auto_{date.today().isoformat()}.db"
    if target.exists():
        try:
            with sqlite3.connect(target) as check:
                if check.execute("PRAGMA integrity_check").fetchone()[0] == "ok":
                    return target
        except sqlite3.Error:
            pass
        target.unlink(missing_ok=True)
    with connect() as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


def verified_backup(prefix: str = "forge") -> Path:
    """Create a consistent SQLite backup, including data still present in WAL."""
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"
    with connect() as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            target.unlink(missing_ok=True)
            raise RuntimeError("Backup integrity check failed")
    return target


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def reconcile_interrupted_timers() -> None:
    """Stop abandoned sessions at the last heartbeat, never at the next launch time."""
    with connect() as con:
        row = con.execute("SELECT value FROM app_meta WHERE key='last_heartbeat'").fetchone()
        heartbeat = _parse_iso(row["value"] if row else None)
        now = datetime.now(timezone.utc)
        for session in con.execute("SELECT id,mission_id,started_at FROM timer_sessions WHERE stopped_at IS NULL").fetchall():
            started = _parse_iso(session["started_at"]) or now
            stopped = max(started, min(now, heartbeat or started))
            elapsed = max(0, int((stopped - started).total_seconds()))
            con.execute("UPDATE timer_sessions SET stopped_at=?,elapsed_seconds=? WHERE id=?", (stopped.isoformat(timespec="milliseconds"), elapsed, session["id"]))
            con.execute("UPDATE missions SET timer_state='paused',updated_at=? WHERE id=?", (now_iso(), session["mission_id"]))


def heartbeat(stop_event: threading.Event) -> None:
    while not stop_event.wait(HEARTBEAT_SECONDS):
        with connect() as con:
            con.execute("INSERT INTO app_meta(key,value) VALUES('last_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now_iso(),))


def mission_exists(con: sqlite3.Connection, mission_id: int) -> bool:
    return con.execute("SELECT 1 FROM missions WHERE id=? AND active=1", (mission_id,)).fetchone() is not None


def require_mission(con: sqlite3.Connection, mission_id: int) -> None:
    if not mission_exists(con, mission_id):
        raise LookupError("Mission not found")


def seed_projects(con: sqlite3.Connection) -> None:
    projects = [
        ("Azure & Intune", "study", "Reach practical completion before trial expiry", "Continue managed-app deployment"),
        ("Employment", "employment", "Secure suitable employment", "Complete the next strong employment actions"),
        ("JOLT", "jolt", "Reliable job discovery and decision support", "Verify and merge the current classifier PR"),
        ("VERIDRA", "veridra", "Evidence-led commercial opportunity intelligence", "Validate statistics-safe review analysis"),
        ("Webify", "webify", "Acquire the first customer and recurring revenue", "Complete competitor research"),
        ("Modern Life Inc.", "youtube", "Publish through a repeatable automated workflow", "Validate the transparent asset system"),
    ]
    for name, area, objective, nxt in projects:
        cur = con.execute(
            "INSERT INTO projects(name,area,objective,next_action,updated_at) VALUES(?,?,?,?,?)",
            (name, area, objective, nxt, now_iso()),
        )
        pid = cur.lastrowid
        if name == "Azure & Intune":
            values = [("Foundation and tenant setup", 20, 100), ("Enrollment and identity", 20, 40), ("Compliance and security", 25, 24), ("Applications and updates", 20, 10), ("Troubleshooting and recall", 15, 0)]
        elif name == "Modern Life Inc.":
            values = [("Channel identity and setup", 10, 100), ("Production workflow", 20, 100), ("Episode 1 script and narration", 15, 100), ("Production-quality asset system", 15, 53), ("Full Episode 1 render", 20, 0), ("Packaging and publishing", 10, 0), ("Repeatable automation", 10, 20)]
        elif name == "Webify":
            values = [("Compliance foundation", 15, 100), ("Market and competitor evidence", 20, 10), ("Service packages and pricing", 20, 0), ("Contracts and payment protection", 15, 0), ("Sales workflow and templates", 15, 0), ("First paying customer", 15, 0)]
        elif name == "JOLT":
            values = [("Core workflow", 30, 100), ("Eligibility semantics", 30, 90), ("Review workflow", 20, 85), ("Stable maintenance mode", 20, 45)]
        elif name == "VERIDRA":
            values = [("Discovery and evidence", 25, 100), ("Commercial qualification", 25, 75), ("Review intelligence", 20, 45), ("Sales handoff", 15, 50), ("Production operations", 15, 80)]
        else:
            values = [("Active pipeline", 50, 50), ("Interview conversion", 30, 30), ("Offer secured", 20, 0)]
        for order, (title, weight, progress) in enumerate(values, 1):
            status = "completed" if progress == 100 else "advanced" if progress > 0 else "not_started"
            con.execute(
                "INSERT INTO milestones(project_id,title,weight,progress,status,sort_order) VALUES(?,?,?,?,?,?)",
                (pid, title, weight, progress, status, order),
            )


def link_unlinked_missions(con: sqlite3.Connection) -> None:
    """Attach project work to its project and current active milestone."""
    mappings = {"study": "Azure & Intune", "employment": "Employment", "jolt": "JOLT",
                "veridra": "VERIDRA", "webify": "Webify", "youtube": "Modern Life Inc."}
    for area, name in mappings.items():
        project = con.execute("SELECT id FROM projects WHERE name=? AND active=1", (name,)).fetchone()
        if not project:
            continue
        milestone = con.execute("""SELECT id FROM milestones WHERE project_id=? AND active=1
                                  AND status!='completed' ORDER BY CASE WHEN progress>0 THEN 0 ELSE 1 END,sort_order,id LIMIT 1""",
                                (project["id"],)).fetchone()
        con.execute("""UPDATE missions SET project_id=?,milestone_id=COALESCE(milestone_id,?)
                       WHERE area=? AND active=1 AND project_id IS NULL""",
                    (project["id"], milestone["id"] if milestone else None, area))


def ensure_day(day: str) -> None:
    with connect() as con:
        # Archived missions still prove that this date was initialized. Never
        # silently recreate defaults after the user archives the whole day.
        exists = con.execute("SELECT 1 FROM missions WHERE day=? LIMIT 1", (day,)).fetchone()
        if exists:
            return
        stamp = now_iso()
        for area, title, priority, best, minutes, weight, order in DEFAULT_MISSIONS:
            project = con.execute("SELECT id FROM projects WHERE area=? AND active=1 ORDER BY id LIMIT 1", (area,)).fetchone()
            milestone = con.execute("""SELECT id FROM milestones WHERE project_id=? AND active=1 AND status!='completed'
                                     ORDER BY CASE WHEN progress>0 THEN 0 ELSE 1 END,sort_order,id LIMIT 1""",
                                    (project["id"],)).fetchone() if project else None
            con.execute(
                """INSERT INTO missions(day,area,title,priority,best_time,suggested_minutes,
                score_weight,sort_order,project_id,milestone_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (day, area, title, priority, best, minutes, weight, order,
                 project["id"] if project else None, milestone["id"] if milestone else None, stamp, stamp),
            )


def rows(con: sqlite3.Connection, sql: str, args=()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def timer_seconds(con: sqlite3.Connection, mission_id: int, mode: str | None = None) -> int:
    sql = "SELECT mode,started_at,stopped_at,elapsed_seconds FROM timer_sessions WHERE mission_id=?"
    args: list[object] = [mission_id]
    if mode:
        sql += " AND mode=?"
        args.append(mode)
    total = 0
    now = datetime.now(timezone.utc)
    for r in con.execute(sql, args):
        total += r["elapsed_seconds"]
        if not r["stopped_at"]:
            started = datetime.fromisoformat(r["started_at"])
            total += max(0, int((now - started).total_seconds()))
    adjustment = con.execute("SELECT COALESCE(SUM(adjustment_seconds),0) FROM time_adjustments WHERE mission_id=?", (mission_id,)).fetchone()[0]
    return max(0, total + int(adjustment))


def timer_breakdown(con: sqlite3.Connection, mission_id: int) -> tuple[int, int]:
    measured = 0
    now = datetime.now(timezone.utc)
    for row in con.execute("SELECT started_at,stopped_at,elapsed_seconds FROM timer_sessions WHERE mission_id=? AND mode='focus'", (mission_id,)):
        measured += int(row["elapsed_seconds"])
        if not row["stopped_at"]:
            started = _parse_iso(row["started_at"]) or now
            measured += max(0, int((now - started).total_seconds()))
    adjustment = int(con.execute("SELECT COALESCE(SUM(adjustment_seconds),0) FROM time_adjustments WHERE mission_id=?", (mission_id,)).fetchone()[0])
    return measured, adjustment


def set_focus_seconds(mission_id: int, desired_seconds: int) -> dict:
    if not 0 <= desired_seconds <= 604_800:
        raise ValueError("focused time must be between 0 and 168 hours")
    with TIMER_LOCK:
        with connect() as con:
            require_mission(con, mission_id)
            current = timer_seconds(con, mission_id, "focus")
            difference = desired_seconds - current
            if difference:
                con.execute("INSERT INTO time_adjustments(mission_id,adjustment_seconds,reason,created_at) VALUES(?,?,?,?)", (mission_id, difference, "manual correction", now_iso()))
            measured, adjustment = timer_breakdown(con, mission_id)
            return {"focus_seconds": max(0, measured + adjustment), "measured_seconds": measured, "adjustment_seconds": adjustment}


def close_focus_sessions(con: sqlite3.Connection, mission_id: int | None = None) -> list[int]:
    """Close running focus sessions using Python timestamps for reliable elapsed time."""
    sql = "SELECT id,mission_id,started_at FROM timer_sessions WHERE stopped_at IS NULL AND mode='focus'"
    args: tuple[object, ...] = ()
    if mission_id is not None:
        sql += " AND mission_id=?"
        args = (mission_id,)
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    closed: list[int] = []
    for row in con.execute(sql, args).fetchall():
        started = datetime.fromisoformat(row["started_at"])
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed = max(0, int((now - started).total_seconds()))
        con.execute(
            "UPDATE timer_sessions SET stopped_at=?,elapsed_seconds=? WHERE id=?",
            (stamp, elapsed, row["id"]),
        )
        closed.append(int(row["mission_id"]))
    return closed


def start_focus_timer(mission_id: int) -> None:
    with TIMER_LOCK:
        with connect() as con:
            require_mission(con, mission_id)
            status = con.execute("SELECT status FROM missions WHERE id=?", (mission_id,)).fetchone()[0]
            if status in {"completed", "deferred"}:
                raise ValueError("Completed or deferred work cannot start a timer")
            already_running = con.execute("SELECT 1 FROM timer_sessions WHERE mission_id=? AND stopped_at IS NULL AND mode='focus'", (mission_id,)).fetchone()
            if already_running:
                return
            closed = close_focus_sessions(con)
            for old_id in closed:
                con.execute("UPDATE missions SET timer_state='paused',updated_at=? WHERE id=?", (now_iso(), old_id))
            con.execute(
                "INSERT INTO timer_sessions(mission_id,mode,started_at) VALUES(?,?,?)",
                (mission_id, "focus", now_iso()),
            )
            con.execute("UPDATE missions SET timer_state='running',updated_at=? WHERE id=?", (now_iso(), mission_id))


def pause_focus_timer(mission_id: int) -> None:
    with TIMER_LOCK:
        with connect() as con:
            require_mission(con, mission_id)
            close_focus_sessions(con, mission_id)
            con.execute("UPDATE missions SET timer_state='paused',updated_at=? WHERE id=?", (now_iso(), mission_id))


def finish_focus_timer(mission_id: int) -> None:
    with TIMER_LOCK:
        with connect() as con:
            require_mission(con, mission_id)
            close_focus_sessions(con, mission_id)
            con.execute("UPDATE missions SET timer_state='finished',updated_at=? WHERE id=?", (now_iso(), mission_id))


def day_payload(day: str) -> dict:
    ensure_day(day)
    with connect() as con:
        missions = rows(con, "SELECT * FROM missions WHERE day=? AND active=1 ORDER BY sort_order,id", (day,))
        for m in missions:
            m["focus_seconds"] = timer_seconds(con, m["id"], "focus")
            m["measured_seconds"], m["adjustment_seconds"] = timer_breakdown(con, m["id"])
            running = con.execute("SELECT mode FROM timer_sessions WHERE mission_id=? AND stopped_at IS NULL AND mode='focus' ORDER BY id DESC LIMIT 1", (m["id"],)).fetchone()
            m["running_mode"] = running["mode"] if running else None
            if running:
                m["timer_state"] = "running"
            elif m["timer_state"] == "running":
                m["timer_state"] = "paused"
            icon, label, color = AREAS.get(m["area"], ("•", m["area"], "#64748b"))
            m.update(area_icon=icon, area_label=label, area_color=color)
            samples = [int(row[0]) for row in con.execute(
                """SELECT COALESCE(SUM(ts.elapsed_seconds),0)+COALESCE((SELECT SUM(ta.adjustment_seconds) FROM time_adjustments ta WHERE ta.mission_id=x.id),0)
                   FROM missions x LEFT JOIN timer_sessions ts ON ts.mission_id=x.id
                   WHERE x.id<>? AND x.active=1 AND x.area=? AND COALESCE(x.project_id,0)=COALESCE(?,0)
                     AND x.status IN ('advanced','completed') AND x.day<? GROUP BY x.id
                   ORDER BY x.day DESC LIMIT 10""", (m["id"], m["area"], m["project_id"], day)).fetchall()]
            samples = sorted(value for value in samples if value > 0)
            m["historical_samples"] = len(samples)
            m["historical_median_seconds"] = samples[len(samples)//2] if samples else None
        note = con.execute("SELECT * FROM daily_notes WHERE day=?", (day,)).fetchone()
        return {"day": day, "missions": missions, "note": dict(note) if note else None, "summary": calculate_summary(missions), "projects": projects_payload()}


def calculate_summary(missions: list[dict]) -> dict:
    def factor(mission: dict) -> float:
        if mission["status"] == "completed": return 1
        if mission["status"] == "advanced": return min(0.99, max(0.01, float(mission.get("progress_after", 0)) / 100))
        if mission["status"] == "blocked": return 0.25
        return 0
    professional = [m for m in missions if m["priority"] not in {"support", "close"}]
    sustainability = [m for m in missions if m["priority"] in {"support", "close"}]
    earned = sum(float(m["score_weight"]) * factor(m) for m in professional)
    possible = sum(float(m["score_weight"]) for m in professional) or 1
    support_earned = sum(float(m["score_weight"]) * factor(m) for m in sustainability)
    support_possible = sum(float(m["score_weight"]) for m in sustainability) or 1
    focus = sum(int(m.get("focus_seconds", 0)) for m in missions)
    done = sum(m["status"] == "completed" for m in missions)
    # WIP means work already started, not every mission planned for the day.
    human_wip = sum(m["priority"] in {"keystone", "important"} and m["status"] in {"advanced", "blocked"} for m in missions)
    warnings = []
    running_completed = [m["title"] for m in missions if m["status"] == "completed" and m.get("running_mode")]
    if running_completed:
        warnings.append(f"Completed mission still timing: {running_completed[0]}")
    if focus > 12 * 3600:
        warnings.append(f"Recorded focus is unusually high ({focus // 3600}h {(focus % 3600) // 60}m). Review mission times before export.")
    return {"xp": round(earned, 1), "score": round(10 * earned / possible, 1), "possible": possible,
            "sustainability_xp": round(support_earned, 1), "sustainability_score": round(10 * support_earned / support_possible, 1),
            "sustainability_possible": support_possible, "focus_seconds": focus, "completed": done, "total": len(missions),
            "human_wip": human_wip, "human_wip_limit": 3, "integrity_warnings": warnings}


def projects_payload() -> list[dict]:
    with connect() as con:
        projects = rows(con, "SELECT * FROM projects WHERE active=1 ORDER BY id")
        for p in projects:
            ms = rows(con, "SELECT * FROM milestones WHERE project_id=? AND active=1 ORDER BY sort_order,id", (p["id"],))
            total_weight = sum(float(x["weight"]) for x in ms) or 100
            completion = sum(float(x["weight"]) * float(x["progress"]) / 100 for x in ms) / total_weight * 100
            p["completion"] = round(completion, 1)
            confidence_order = {"low": 0, "medium": 1, "high": 2}
            active_confidence = [confidence_order.get(str(x.get("confidence", "low")), 0) for x in ms if x["status"] != "completed"]
            p["confidence"] = ("low", "medium", "high")[min(active_confidence) if active_confidence else 2]
            p["milestones"] = ms
            icon, label, color = AREAS.get(p["area"], ("•", p["area"], "#64748b"))
            p.update(area_icon=icon, area_color=color)
        return projects


def dashboard_payload(end_day: str) -> dict:
    ensure_day(end_day)
    end = date.fromisoformat(end_day)
    start = end - timedelta(days=6)
    days = []
    area_totals: dict[str, dict] = {}
    total_seconds = completed = keystone_advanced = keystone_total = active_days = 0
    planned_minutes = rollover_count = 0
    energy_points = []
    performance_points = []
    linked_project_ids: set[int] = set()
    project_progress: dict[int, float] = {}
    score_total = 0.0
    with connect() as con:
        for offset in range(7):
            current = (start + timedelta(days=offset)).isoformat()
            missions = rows(con, "SELECT * FROM missions WHERE day=? AND active=1 ORDER BY sort_order,id", (current,))
            for mission in missions:
                mission["focus_seconds"] = timer_seconds(con, mission["id"], "focus")
                icon, label, color = AREAS.get(mission["area"], ("•", mission["area"], "#64748b"))
                bucket = area_totals.setdefault(mission["area"], {"area": mission["area"], "icon": icon, "label": label, "color": color, "focus_seconds": 0, "xp": 0.0})
                bucket["focus_seconds"] += mission["focus_seconds"]
                factor = 1 if mission["status"] == "completed" else min(.99, max(.01, float(mission["progress_after"] or 0)/100)) if mission["status"] == "advanced" else .25 if mission["status"] == "blocked" else 0
                bucket["xp"] += float(mission["score_weight"]) * factor
                planned_minutes += int(mission["suggested_minutes"] or 0)
                if mission["rollover_from_id"]: rollover_count += 1
                if mission["project_id"]:
                    project_id = int(mission["project_id"])
                    linked_project_ids.add(project_id)
                    project_progress[project_id] = project_progress.get(project_id, 0) + max(0, float(mission["progress_after"] or 0) - float(mission["progress_before"] or 0))
            summary = calculate_summary(missions)
            seconds = summary["focus_seconds"]
            day_keystones = [m for m in missions if m["priority"] == "keystone"]
            advanced = sum(m["status"] in {"advanced", "completed"} for m in day_keystones)
            days.append({"day": current, "label": (start + timedelta(days=offset)).strftime("%a"), "focus_seconds": seconds, "score": summary["score"], "completed": summary["completed"], "keystones_advanced": advanced, "keystones_total": len(day_keystones)})
            total_seconds += seconds
            completed += summary["completed"]
            keystone_advanced += advanced
            keystone_total += len(day_keystones)
            if missions and (seconds > 0 or any(m["status"] != "not_started" for m in missions)):
                active_days += 1
                score_total += summary["score"]
            note = con.execute("SELECT energy_start,energy_end FROM daily_notes WHERE day=?", (current,)).fetchone()
            if note and note["energy_start"] is not None and note["energy_end"] is not None:
                energy_points.append({"day": current, "label": (start + timedelta(days=offset)).strftime("%a"), "start": note["energy_start"], "end": note["energy_end"]})
            local_buckets: dict[int, dict] = {}
            session_now = datetime.now(timezone.utc)
            for session in con.execute("""SELECT ts.started_at,ts.stopped_at,ts.elapsed_seconds,m.id,m.status
                FROM timer_sessions ts JOIN missions m ON m.id=ts.mission_id
                WHERE m.day=? AND ts.mode='focus'""", (current,)):
                started = _parse_iso(session["started_at"]) or session_now
                hour = started.astimezone().hour
                elapsed = int(session["elapsed_seconds"] or 0)
                if not session["stopped_at"]:
                    elapsed += max(0, int((session_now - started).total_seconds()))
                bucket = local_buckets.setdefault(hour, {"seconds": 0, "outcome_ids": set()})
                bucket["seconds"] += elapsed
                if session["status"] in {"advanced", "completed"}:
                    bucket["outcome_ids"].add(int(session["id"]))
            performance_points.extend({"hour": hour, "seconds": values["seconds"], "outcomes": len(values["outcome_ids"])} for hour, values in local_buckets.items())
        blockers = rows(con, """SELECT m.id,m.title,m.blocker_reason,m.day,p.name AS project_name,
            CAST(julianday(?) - julianday(m.day) AS INTEGER) AS age_days
            FROM missions m LEFT JOIN projects p ON p.id=m.project_id
            WHERE m.active=1 AND m.blocker_active=1 ORDER BY age_days DESC,m.id""", (end_day,))
        decisions = rows(con, "SELECT * FROM planning_decisions WHERE day BETWEEN ? AND ? ORDER BY created_at DESC", (start.isoformat(), end_day))
    areas = sorted(area_totals.values(), key=lambda item: (item["focus_seconds"], item["xp"]), reverse=True)
    for item in areas:
        item["xp"] = round(item["xp"], 1)
    project_rows = projects_payload()
    neglected = [{"name": p["name"], "icon": p["area_icon"], "next_action": p["next_action"]} for p in project_rows if int(p["id"]) not in linked_project_ids]
    return {
        "start_day": start.isoformat(), "end_day": end_day, "days": days, "areas": areas,
        "summary": {"focus_seconds": total_seconds, "average_daily_seconds": round(total_seconds / active_days) if active_days else 0, "average_score": round(score_total / active_days, 1) if active_days else 0, "completed": completed, "keystones_advanced": keystone_advanced, "keystones_total": keystone_total, "active_days": active_days, "planned_minutes": planned_minutes, "planned_seconds": planned_minutes*60, "time_fit": max(0, round(100 - abs(total_seconds-planned_minutes*60)/(planned_minutes*60)*100)) if planned_minutes else 0, "time_variance_minutes": round((total_seconds-planned_minutes*60)/60) if planned_minutes else 0, "rollover_count": rollover_count},
        "energy": energy_points, "performance": performance_points, "blockers": blockers, "decisions": decisions,
        "neglected_projects": neglected,
        "projects": [{"name": p["name"], "icon": p["area_icon"], "color": p["area_color"], "completion": p["completion"], "next_action": p["next_action"], "weekly_mission_progress": round(project_progress.get(int(p["id"]), 0), 1)} for p in project_rows],
    }


def export_handoff(day: str) -> Path:
    payload = day_payload(day)
    projects = projects_payload()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"FORGE_HANDOFF_{day}_{stamp}"
    folder = EXPORTS / base
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "daily_state.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "projects.json").write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# FORGE Daily Handoff — {day}", "", f"**Score:** {payload['summary']['score']}/10 · **XP:** {payload['summary']['xp']}/{payload['summary']['possible']}", "", "## Daily missions", ""]
    for m in payload["missions"]:
        manual = int(m.get("adjustment_seconds", 0))
        correction = f" · manual correction {manual / 60:+.1f} min" if manual else ""
        project = next((p for p in projects if p["id"] == m.get("project_id")), None)
        milestone = next((x for x in (project or {}).get("milestones", []) if x["id"] == m.get("milestone_id")), None)
        lines += [f"### {m['area_icon']} {m['area_label']} — {m['status'].replace('_',' ').title()}", f"**Mission:** {m['title']}", f"**Linked:** {(project or {}).get('name','None')}{' / '+milestone['title'] if milestone else ''}", f"**Progress:** {m.get('progress_after',0)}%", f"**Success evidence:** {m.get('success_evidence') or 'Not defined'}", f"**Result:** {m['result'] or 'Not recorded'}", f"**Next:** {m['next_action'] or 'Not defined'}", f"**Resume from:** {m.get('resume_location') or 'Not recorded'}", f"**Blocker:** {m.get('blocker_reason') or 'None'}", f"**If–then cue:** {m.get('if_then_cue') or 'Not defined'}", f"**Focused time:** {m['focus_seconds']//60} min{correction}", ""]
    note = payload.get("note") or {}
    lines += ["## Daily close", "", f"**Energy:** {note.get('energy_start', '—')} → {note.get('energy_end', '—')}", f"**Reflection:** {note.get('reflection') or 'Not recorded'}", f"**Tomorrow’s keystone:** {note.get('tomorrow_focus') or 'Not defined'}", ""]
    lines += ["## Project state", ""]
    for p in projects:
        lines.append(f"- {p['area_icon']} **{p['name']}: {p['completion']}%** — Next: {p['next_action']}")
    (folder / "journal.md").write_text("\n".join(lines), encoding="utf-8")
    archive = EXPORTS / f"{base}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in folder.iterdir():
            zf.write(f, f.name)
    shutil.rmtree(folder)
    return archive


def export_json_handoff(day: str) -> Path:
    """Create one self-describing, portable snapshot for a planning chat."""
    payload = day_payload(day)
    export_id = f"forge-{day}-{uuid.uuid4().hex[:12]}"
    end = date.fromisoformat(day)
    detail_start = (end - timedelta(days=13)).isoformat()
    with connect() as con:
        history = []
        for history_day in rows(con, "SELECT DISTINCT day FROM missions WHERE day BETWEEN ? AND ? ORDER BY day", (detail_start, day)):
            history.append(day_payload(history_day["day"]))
        older = rows(con, """SELECT substr(day,1,7) AS month,COUNT(DISTINCT day) AS days,
            COUNT(*) AS missions,SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed
            FROM missions WHERE day<? GROUP BY substr(day,1,7) ORDER BY month DESC""", (detail_start,))
        decisions = rows(con, "SELECT * FROM planning_decisions ORDER BY created_at DESC LIMIT 100")
        study = rows(con, """SELECT sr.*,m.day,m.title,m.area FROM study_reviews sr
            JOIN missions m ON m.id=sr.mission_id ORDER BY COALESCE(sr.next_review_day,m.day),sr.id""")
    document = {
        "protocol": "forge-snapshot",
        "schema_version": "2.0",
        "export_id": export_id,
        "app_version": APP_VERSION,
        "exported_at": now_iso(),
        "date": day,
        "purpose": "Portable FORGE evidence snapshot for external planning and analysis",
        "current_day": {"date": day, "summary": payload["summary"], "note": payload.get("note"), "missions": payload["missions"]},
        "projects": payload["projects"],
        "history": {"detailed_days": history, "older_months": older},
        "study_reviews": study,
        "planning_decisions": decisions,
        "planning_constraints": {"planning_owner": "ChatGPT", "execution_owner": "FORGE", "maximum_human_focus_missions": 3, "parallel_areas": ["jolt", "veridra"], "times_are_guidance": True, "prefer_milestones_over_hours": True},
        "blockers": [{"mission_id": m["id"], "title": m["title"], "reason": m.get("blocker_reason", "")} for m in payload["missions"] if m.get("blocker_active")],
        "tomorrow_candidates": [{"mission_id": m["id"], "title": m["title"], "next_action": m.get("next_action", ""), "project_id": m.get("project_id"), "milestone_id": m.get("milestone_id")} for m in payload["missions"] if m["status"] not in {"completed", "deferred"}],
        "chatgpt_instructions": [
            "Analyse outcomes, blockers, time fit, energy patterns and project evidence.",
            "Plan outside FORGE. Return only one valid JSON object using the return_contract.",
            "Use stable ids from this snapshot; never invent target ids.",
            "Create at most three human-focus missions; JOLT and VERIDRA may remain parallel.",
            "Do not alter measured timer history or overwrite recorded evidence.",
            "Treat milestone percentages as evidence estimates and include confidence and completion conditions.",
        ],
        "return_contract": {"protocol": "forge-ai-plan", "schema_version": "2.0", "based_on_export": export_id, "plan_date": "YYYY-MM-DD", "warnings": ["text"], "operations": [{"id": "stable unique text", "action": "create_mission | update_mission | update_project | update_milestone | add_decision | update_study_review", "target_id": "existing numeric id when updating", "data_or_changes": "fields", "label": "plain visual description", "reason": "why"}]},
    }
    EXPORTS.mkdir(exist_ok=True)
    target = EXPORTS / f"FORGE_HANDOFF_{day}.json"
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    with connect() as con:
        con.execute("INSERT INTO app_meta(key,value) VALUES('last_export_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (export_id,))
        con.execute("INSERT INTO app_meta(key,value) VALUES('last_exported_at',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (document["exported_at"],))
    return target


def validate_ai_plan(plan: dict) -> dict:
    if not isinstance(plan, dict): raise ValueError("AI plan must be a JSON object")
    if plan.get("protocol") != "forge-ai-plan": raise ValueError("This is not a FORGE AI plan")
    if plan.get("schema_version") not in {"1.0", "2.0"}: raise ValueError("Unsupported FORGE AI plan version")
    plan_date = valid_day(plan.get("plan_date", date.today().isoformat()))
    raw_operations = plan.get("operations", [])
    if not isinstance(raw_operations, list) or len(raw_operations) > 100: raise ValueError("operations must be a list of at most 100 items")
    warnings = plan.get("warnings", [])
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings): raise ValueError("warnings must be a list of text items")
    warnings = [bounded_text(item, "warning") for item in warnings]
    based_on_export = plan.get("based_on_export")
    with connect() as meta_con:
        last = meta_con.execute("SELECT value FROM app_meta WHERE key='last_export_id'").fetchone()
    if last and based_on_export != last[0]: warnings.append("STALE PLAN: it does not reference the latest FORGE export and cannot be applied.")
    normalized = []
    seen = set()
    with connect() as con:
        for index, raw in enumerate(raw_operations):
            if not isinstance(raw, dict): raise ValueError(f"Operation {index+1} must be an object")
            operation_id = bounded_text(raw.get("id", f"op-{index+1}"), "operation id", True)
            if operation_id in seen: raise ValueError("Operation ids must be unique")
            seen.add(operation_id)
            action = raw.get("action")
            risk = "normal"; selected = True; target_id = raw.get("target_id"); before = None
            if action == "create_mission":
                data = normalize_mission_fields(raw.get("data", {}), True)
                data["day"] = valid_day(raw.get("data", {}).get("day", plan_date))
                label = f"Add {data['title']} to {data['day']}"
            elif action == "update_mission":
                target_id = int(target_id); current = con.execute("SELECT * FROM missions WHERE id=? AND active=1", (target_id,)).fetchone()
                if current is None: raise ValueError(f"Mission {target_id} was not found")
                data = normalize_mission_fields(raw.get("changes", {}))
                if not data: raise ValueError(f"Operation {operation_id} has no valid mission changes")
                label = f"Update mission: {current['title']}"
                before = {key: current[key] for key in data}
            elif action == "update_project":
                target_id = int(target_id); current = con.execute("SELECT * FROM projects WHERE id=? AND active=1", (target_id,)).fetchone()
                if current is None: raise ValueError(f"Project {target_id} was not found")
                data = normalize_project_fields(raw.get("changes", {}))
                data.pop("active", None)
                if not data: raise ValueError(f"Operation {operation_id} has no valid project changes")
                label = f"Update project: {current['name']}"
                before = {key: current[key] for key in data}
            elif action == "update_milestone":
                target_id = int(target_id); current = con.execute("SELECT * FROM milestones WHERE id=? AND active=1", (target_id,)).fetchone()
                if current is None: raise ValueError(f"Milestone {target_id} was not found")
                data = normalize_milestone_fields(raw.get("changes", {}))
                if not data: raise ValueError(f"Operation {operation_id} has no valid milestone changes")
                if "progress" in data and float(data["progress"]) < float(current["progress"]): risk = "review"; selected = False
                label = f"Update milestone: {current['title']}"
                before = {key: current[key] for key in data}
            elif action == "add_decision":
                raw_data = raw.get("data", {})
                data = {"day": valid_day(raw_data.get("day", plan_date)), "decision": bounded_text(raw_data.get("decision", ""), "decision", True), "reason": bounded_text(raw_data.get("reason", ""), "reason")}
                label = f"Record decision: {data['decision']}"
            elif action == "update_study_review":
                target_id = int(target_id)
                current = con.execute("SELECT title FROM missions WHERE id=? AND active=1 AND area='study'", (target_id,)).fetchone()
                if current is None: raise ValueError(f"Study mission {target_id} was not found")
                changes = raw.get("changes", {})
                data = {key: changes[key] for key in ("recall", "practice", "next_review_day") if key in changes}
                if "recall" in data and data["recall"] not in {"weak", "partial", "solid"}: raise ValueError("recall must be weak, partial or solid")
                if "practice" in data and data["practice"] not in {"not_tested", "partial", "passed"}: raise ValueError("practice must be not_tested, partial or passed")
                if "next_review_day" in data: data["next_review_day"] = valid_day(data["next_review_day"])
                if not data: raise ValueError("Study review has no valid changes")
                label = f"Schedule study review: {current['title']}"
            else:
                raise ValueError(f"Unsupported action: {action}")
            normalized.append({"id": operation_id, "action": action, "target_id": target_id, "data": data, "before": before, "label": bounded_text(raw.get("label", label), "label"), "reason": bounded_text(raw.get("reason", ""), "reason"), "risk": risk, "default_selected": selected})
    if plan.get("project_map"):
        warnings.append("The project map is visual guidance; only the listed operations change FORGE.")
    return {"protocol": "forge-ai-plan-preview", "schema_version": "2.0", "based_on_export": based_on_export, "plan_date": plan_date, "operations": normalized, "warnings": warnings}


def apply_ai_plan(plan: dict, selected_ids: list[str]) -> dict:
    preview = validate_ai_plan(plan)
    selected = set(selected_ids)
    unknown = selected - {item["id"] for item in preview["operations"]}
    if unknown: raise ValueError("Unknown selected operation")
    plan_key = hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with connect() as con:
        latest = con.execute("SELECT value FROM app_meta WHERE key='last_export_id'").fetchone()
        exported = con.execute("SELECT value FROM app_meta WHERE key='last_exported_at'").fetchone()
        if latest and plan.get("based_on_export") != latest[0]:
            raise ValueError("This AI plan is stale. Export FORGE again and generate a new plan.")
        already = {row[0] for row in con.execute("SELECT operation_id FROM ai_import_operations WHERE plan_key=?", (plan_key,))}
        repeated = selected & already
        if repeated:
            raise ValueError("Selected AI changes were already applied; nothing was duplicated.")
        export_time = exported[0] if exported else None
        for item in preview["operations"]:
            if item["id"] not in selected or item["action"] == "create_mission" or not export_time:
                continue
            if item["action"] in {"add_decision", "update_study_review"}: continue
            table = {"update_mission": "missions", "update_project": "projects", "update_milestone": "milestones"}[item["action"]]
            changed = con.execute(f"SELECT updated_at FROM {table} WHERE id=?", (item["target_id"],)).fetchone()
            if changed and changed[0] and changed[0] > export_time:
                raise ValueError(f"{item['label']} changed after export. Export again before applying this plan.")
    backup = verified_backup("forge_pre_ai_import")
    applied = []
    with connect() as con:
        for item in preview["operations"]:
            if item["id"] not in selected: continue
            action, data, target_id = item["action"], dict(item["data"]), item["target_id"]
            if action == "create_mission":
                day = data.pop("day"); stamp = now_iso()
                if data.get("project_id") is not None and con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (data["project_id"],)).fetchone() is None: raise ValueError("Linked project not found")
                if data.get("milestone_id") is not None:
                    linked = con.execute("SELECT project_id FROM milestones WHERE id=? AND active=1", (data["milestone_id"],)).fetchone()
                    if linked is None or int(linked[0]) != int(data.get("project_id") or 0): raise ValueError("Milestone must belong to the linked project")
                con.execute("""INSERT INTO missions(day,area,title,priority,best_time,suggested_minutes,status,result,next_action,progress_before,progress_after,score_weight,sort_order,project_id,milestone_id,success_evidence,resume_location,blocker_reason,if_then_cue,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (day,data.get("area","orchestration"),data["title"],data.get("priority","important"),data.get("best_time","Anytime"),data.get("suggested_minutes",30),data.get("status","not_started"),data.get("result",""),data.get("next_action",""),data.get("progress_before",0),data.get("progress_after",0),data.get("score_weight",10),data.get("sort_order",999),data.get("project_id"),data.get("milestone_id"),data.get("success_evidence",""),data.get("resume_location",""),data.get("blocker_reason",""),data.get("if_then_cue",""),stamp,stamp))
            elif action == "update_mission":
                data = harmonize_mission_fields(con, target_id, data); data["updated_at"] = now_iso()
                if data.get("status") == "completed":
                    close_focus_sessions(con, target_id)
                    data["timer_state"] = "finished"
                con.execute("UPDATE missions SET "+",".join(f"{key}=?" for key in data)+" WHERE id=?", [*data.values(), target_id])
            elif action == "update_project":
                data["updated_at"] = now_iso(); con.execute("UPDATE projects SET "+",".join(f"{key}=?" for key in data)+" WHERE id=?", [*data.values(), target_id])
            elif action == "update_milestone":
                data = harmonize_milestone_fields(data)
                data["updated_at"] = now_iso()
                con.execute("UPDATE milestones SET "+",".join(f"{key}=?" for key in data)+" WHERE id=?", [*data.values(), target_id])
            elif action == "add_decision":
                con.execute("INSERT INTO planning_decisions(day,decision,reason,source,created_at) VALUES(?,?,?,?,?)", (data["day"], data["decision"], data.get("reason", ""), "chatgpt", now_iso()))
            elif action == "update_study_review":
                current = con.execute("SELECT recall,practice,next_review_day FROM study_reviews WHERE mission_id=?", (target_id,)).fetchone()
                merged = dict(current) if current else {"recall": None, "practice": None, "next_review_day": None}
                merged.update(data)
                con.execute("""INSERT INTO study_reviews(mission_id,recall,practice,next_review_day,updated_at) VALUES(?,?,?,?,?)
                    ON CONFLICT(mission_id) DO UPDATE SET recall=excluded.recall,practice=excluded.practice,next_review_day=excluded.next_review_day,updated_at=excluded.updated_at""",
                    (target_id, merged["recall"], merged["practice"], merged["next_review_day"], now_iso()))
            con.execute("INSERT INTO ai_import_operations(plan_key,operation_id,action,applied_at) VALUES(?,?,?,?)",
                        (plan_key, item["id"], action, now_iso()))
            applied.append(item["id"])
    return {"ok": True, "applied": len(applied), "applied_ids": applied, "backup": backup.name}


def prepare_tomorrow(source_day: str, target_day: str, mission_ids: list[int]) -> dict:
    if date.fromisoformat(target_day) <= date.fromisoformat(source_day): raise ValueError("Tomorrow must be after the source day")
    with connect() as con:
        valid_ids = {int(row[0]) for row in con.execute("SELECT id FROM missions WHERE day=? AND active=1 AND status NOT IN ('completed','deferred')", (source_day,))}
    requested = [int(item) for item in mission_ids]
    if any(item not in valid_ids for item in requested): raise ValueError("A selected mission is not an unfinished mission from this day")
    results = [rollover_mission(item, target_day, "replace") for item in requested]
    return {"ok": True, "target_day": target_day, "prepared": len(results), "results": results}


def valid_day(value: object) -> str:
    text = str(value)
    date.fromisoformat(text)
    return text


def bounded_number(value: object, low: float, high: float, name: str) -> float:
    number = float(value)
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}")
    return number


def bounded_text(value: object, name: str, required: bool = False) -> str:
    text = str(value).strip() if required else str(value)
    if required and not text:
        raise ValueError(f"{name} is required")
    if len(text) > MAX_TEXT:
        raise ValueError(f"{name} is too long")
    return text


def normalize_mission_fields(data: dict, creating: bool = False) -> dict:
    allowed = {"title", "priority", "best_time", "suggested_minutes", "status", "result", "next_action", "progress_before", "progress_after", "score_weight", "sort_order", "area", "project_id", "milestone_id", "success_evidence", "resume_location", "blocker_reason", "blocker_active", "if_then_cue"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if creating or "title" in fields: fields["title"] = bounded_text(fields.get("title", ""), "title", True)
    for key in ("best_time", "result", "next_action", "success_evidence", "resume_location", "blocker_reason", "if_then_cue"):
        if key in fields: fields[key] = bounded_text(fields[key], key)
    if "area" in fields and fields["area"] not in AREAS: raise ValueError("Unknown area")
    if "priority" in fields and fields["priority"] not in VALID_PRIORITIES: raise ValueError("Unknown priority")
    if "status" in fields and fields["status"] not in VALID_STATUSES: raise ValueError("Unknown status")
    if "suggested_minutes" in fields: fields["suggested_minutes"] = int(bounded_number(fields["suggested_minutes"], 0, 1440, "suggested_minutes"))
    for key in ("progress_before", "progress_after", "score_weight"):
        if key in fields: fields[key] = bounded_number(fields[key], 0, 100, key)
    if "sort_order" in fields: fields["sort_order"] = int(bounded_number(fields["sort_order"], 0, 1_000_000, "sort_order"))
    for key in ("project_id", "milestone_id"):
        if key in fields: fields[key] = int(fields[key]) if fields[key] not in (None, "", 0, "0") else None
    if "blocker_active" in fields: fields["blocker_active"] = 1 if bool(fields["blocker_active"]) else 0
    if "blocker_reason" in fields and "blocker_active" not in fields: fields["blocker_active"] = 1 if fields["blocker_reason"].strip() else 0
    return fields


def harmonize_mission_fields(con: sqlite3.Connection, mission_id: int, fields: dict) -> dict:
    current = con.execute("SELECT status,progress_after,blocker_reason FROM missions WHERE id=? AND active=1", (mission_id,)).fetchone()
    if current is None: raise LookupError("Mission not found")
    if "project_id" in fields and fields["project_id"] is not None:
        if con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (fields["project_id"],)).fetchone() is None: raise ValueError("Linked project not found")
    project_id = fields.get("project_id", con.execute("SELECT project_id FROM missions WHERE id=?", (mission_id,)).fetchone()[0])
    if "milestone_id" in fields and fields["milestone_id"] is not None:
        row = con.execute("SELECT project_id FROM milestones WHERE id=? AND active=1", (fields["milestone_id"],)).fetchone()
        if row is None or project_id is None or int(row[0]) != int(project_id): raise ValueError("Milestone must belong to the linked project")
    if fields.get("project_id", "unchanged") is None and "project_id" in fields:
        fields["milestone_id"] = None
    if "status" in fields:
        if fields["status"] == "completed":
            fields["blocker_active"] = 0
            fields["progress_after"] = 100
        elif fields["status"] == "not_started": fields["progress_after"] = 0
        elif fields["status"] == "advanced" and float(fields.get("progress_after", current["progress_after"] or 0)) <= 0: fields["progress_after"] = 50
    elif "progress_after" in fields:
        progress = float(fields["progress_after"])
        fields["status"] = "completed" if progress >= 100 else "not_started" if progress <= 0 else "advanced"
    return fields


def normalize_project_fields(data: dict, creating: bool = False) -> dict:
    allowed = {"name", "area", "objective", "next_action", "active", "priority_rank"}
    fields = {key: value for key, value in data.items() if key in allowed}
    if creating or "name" in fields: fields["name"] = bounded_text(fields.get("name", ""), "name", True)
    for key in ("objective", "next_action"):
        if key in fields: fields[key] = bounded_text(fields[key], key)
    if "area" in fields and fields["area"] not in AREAS: raise ValueError("Unknown area")
    if "active" in fields: fields["active"] = 1 if bool(fields["active"]) else 0
    if "priority_rank" in fields: fields["priority_rank"] = int(bounded_number(fields["priority_rank"], 1, 999, "priority_rank"))
    return fields


def normalize_milestone_fields(data: dict, creating: bool = False) -> dict:
    allowed = {"title", "weight", "progress", "status", "evidence", "sort_order", "confidence", "completion_conditions"}
    fields = {key: value for key, value in data.items() if key in allowed}
    if creating or "title" in fields: fields["title"] = bounded_text(fields.get("title", ""), "title", True)
    for key in ("evidence", "completion_conditions"):
        if key in fields: fields[key] = bounded_text(fields[key], key)
    if "confidence" in fields and fields["confidence"] not in {"low", "medium", "high"}: raise ValueError("confidence must be low, medium or high")
    if "weight" in fields: fields["weight"] = bounded_number(fields["weight"], 0, 100, "weight")
    if "progress" in fields: fields["progress"] = bounded_number(fields["progress"], 0, 100, "progress")
    if "status" in fields and fields["status"] not in VALID_STATUSES: raise ValueError("Unknown status")
    if "sort_order" in fields: fields["sort_order"] = int(bounded_number(fields["sort_order"], 0, 1_000_000, "sort_order"))
    return fields


def harmonize_milestone_fields(fields: dict) -> dict:
    """Keep milestone progress and status as one consistent state."""
    if "progress" in fields:
        progress = float(fields["progress"])
        fields["status"] = "completed" if progress >= 100 else "not_started" if progress <= 0 else "advanced"
    elif "status" in fields:
        if fields["status"] == "completed":
            fields["progress"] = 100
        elif fields["status"] == "not_started":
            fields["progress"] = 0
    return fields


def complete_mission(mission_id: int, milestone_update: dict | None = None, resolve_blocker: bool = False) -> None:
    """Complete a mission and its optional milestone in one transaction."""
    with TIMER_LOCK:
        with connect() as con:
            require_mission(con, mission_id)
            current = con.execute("SELECT blocker_reason,blocker_active,milestone_id FROM missions WHERE id=?", (mission_id,)).fetchone()
            if current["blocker_active"] and not resolve_blocker:
                raise ValueError("This mission has an active blocker. Resolve it before completion.")
            close_focus_sessions(con, mission_id)
            con.execute("""UPDATE missions SET status='completed',progress_after=100,timer_state='finished',
                           blocker_active=0,updated_at=? WHERE id=?""", (now_iso(), mission_id))
            if milestone_update is not None:
                milestone_id = int(milestone_update.get("id") or current["milestone_id"] or 0)
                if not milestone_id or int(current["milestone_id"] or 0) != milestone_id:
                    raise ValueError("Milestone does not belong to this mission")
                fields = harmonize_milestone_fields(normalize_milestone_fields(milestone_update))
                fields.pop("id", None)
                if fields:
                    fields["updated_at"] = now_iso()
                    con.execute("UPDATE milestones SET "+",".join(f"{key}=?" for key in fields)+" WHERE id=? AND active=1",
                                [*fields.values(), milestone_id])


def restore_item(kind: str, item_id: int) -> None:
    table = {"mission": "missions", "project": "projects", "milestone": "milestones"}.get(kind)
    if not table: raise ValueError("Unknown archive type")
    with connect() as con:
        if con.execute(f"SELECT 1 FROM {table} WHERE id=? AND active=0", (item_id,)).fetchone() is None: raise LookupError("Archived item not found")
        if kind == "project":
            con.execute("UPDATE projects SET active=1,updated_at=? WHERE id=?", (now_iso(), item_id))
        elif kind == "mission":
            parent = con.execute("SELECT project_id FROM missions WHERE id=?", (item_id,)).fetchone()
            if parent and parent["project_id"]: con.execute("UPDATE projects SET active=1,updated_at=? WHERE id=?", (now_iso(), parent["project_id"]))
            con.execute("UPDATE missions SET active=1,updated_at=? WHERE id=?", (now_iso(), item_id))
        else:
            parent = con.execute("SELECT project_id FROM milestones WHERE id=?", (item_id,)).fetchone()
            if parent: con.execute("UPDATE projects SET active=1,updated_at=? WHERE id=?", (now_iso(), parent["project_id"]))
            con.execute("UPDATE milestones SET active=1 WHERE id=?", (item_id,))


def rollover_mission(mission_id: int, target_day: str, mode: str = "continue") -> dict:
    if mode not in {"continue", "replace", "defer"}: raise ValueError("Unknown rollover mode")
    stamp = now_iso()
    with connect() as con:
        source = con.execute("SELECT * FROM missions WHERE id=? AND active=1", (mission_id,)).fetchone()
        if source is None: raise LookupError("Mission not found")
        if mode == "defer":
            close_focus_sessions(con, mission_id)
            con.execute("UPDATE missions SET status='deferred',timer_state='finished',updated_at=? WHERE id=?", (stamp, mission_id))
            return {"ok": True, "deferred": True}
    ensure_day(target_day)
    with connect() as con:
        source = con.execute("SELECT * FROM missions WHERE id=? AND active=1", (mission_id,)).fetchone()
        existing = con.execute("SELECT id FROM missions WHERE rollover_from_id=? AND day=? AND active=1", (mission_id, target_day)).fetchone()
        if existing: return {"ok": True, "id": existing["id"], "existing": True}
        replaced = None
        if mode == "replace":
            replaced = con.execute("""SELECT id FROM missions WHERE day=? AND area=? AND active=1 AND rollover_from_id IS NULL
              AND status IN ('not_started','deferred') AND COALESCE(result,'')='' ORDER BY sort_order,id LIMIT 1""", (target_day, source["area"])).fetchone()
            if replaced: con.execute("UPDATE missions SET active=0,updated_at=? WHERE id=?", (stamp, replaced["id"]))
        title = source["next_action"].strip() or source["title"]
        cur = con.execute("""INSERT INTO missions(day,area,title,priority,best_time,suggested_minutes,status,result,next_action,progress_before,progress_after,score_weight,timer_state,project_id,milestone_id,success_evidence,resume_location,blocker_reason,if_then_cue,rollover_from_id,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (target_day,source["area"],title,source["priority"],source["best_time"],source["suggested_minutes"],"not_started","","",0,0,source["score_weight"],"idle",source["project_id"],source["milestone_id"],source["success_evidence"],source["resume_location"],"",source["if_then_cue"],mission_id,source["sort_order"],stamp,stamp))
        return {"ok": True, "id": cur.lastrowid, "existing": False, "replaced": int(replaced["id"]) if replaced else None}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[FORGE] {self.address_string()} - {fmt % args}")

    def send_json(self, obj, status=200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size > 1_000_000:
            raise ValueError("Request body is too large")
        payload = json.loads(self.rfile.read(size) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/identity":
            return self.send_json({"app": "FORGE", "version": APP_VERSION})
        if parsed.path == "/api/day":
            try:
                day = valid_day(parse_qs(parsed.query).get("date", [date.today().isoformat()])[0])
            except ValueError as exc:
                return self.send_json({"error": str(exc)}, 400)
            return self.send_json(day_payload(day))
        if parsed.path == "/api/projects":
            return self.send_json(projects_payload())
        if parsed.path == "/api/dashboard":
            try:
                selected = valid_day(parse_qs(parsed.query).get("date", [date.today().isoformat()])[0])
                return self.send_json(dashboard_payload(selected))
            except ValueError as exc:
                return self.send_json({"error": str(exc)}, 400)
        if parsed.path == "/api/archive":
            with connect() as con:
                missions = rows(con, "SELECT id,day,area,title,'mission' AS kind FROM missions WHERE active=0 ORDER BY updated_at DESC LIMIT 200")
                projects = rows(con, "SELECT id,name AS title,area,'project' AS kind FROM projects WHERE active=0 ORDER BY updated_at DESC LIMIT 100")
                milestones = rows(con, "SELECT m.id,m.title,p.name AS project_name,'milestone' AS kind FROM milestones m JOIN projects p ON p.id=m.project_id WHERE m.active=0 ORDER BY m.id DESC LIMIT 200")
            return self.send_json({"missions": missions, "projects": projects, "milestones": milestones})
        if parsed.path.startswith("/downloads/"):
            target = EXPORTS / Path(parsed.path).name
            if not target.exists():
                return self.send_error(404)
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8" if target.suffix == ".json" else "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data); return
        target = STATIC / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
        if target.is_file() and STATIC in target.resolve().parents:
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data); return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/timer/start":
                data = self.body(); mid = int(data["mission_id"])
                start_focus_timer(mid)
                return self.send_json({"ok": True})
            if parsed.path == "/api/timer/pause":
                data = self.body(); mid = int(data["mission_id"])
                pause_focus_timer(mid)
                return self.send_json({"ok": True})
            if parsed.path == "/api/timer/finish":
                data = self.body(); mid = int(data["mission_id"])
                finish_focus_timer(mid)
                return self.send_json({"ok": True})
            if parsed.path == "/api/timer/set":
                data = self.body(); mid = int(data["mission_id"])
                desired = int(bounded_number(data["focus_seconds"], 0, 604_800, "focused time"))
                return self.send_json({"ok": True, **set_focus_seconds(mid, desired)})
            if parsed.path == "/api/mission/complete":
                data = self.body()
                complete_mission(int(data["mission_id"]), data.get("milestone"), bool(data.get("resolve_blocker", False)))
                return self.send_json({"ok": True})
            if parsed.path == "/api/export":
                archive = export_handoff(valid_day(self.body().get("day", date.today().isoformat())))
                return self.send_json({"ok": True, "filename": archive.name, "url": f"/downloads/{archive.name}"})
            if parsed.path == "/api/export-json":
                target = export_json_handoff(valid_day(self.body().get("day", date.today().isoformat())))
                return self.send_json({"ok": True, "filename": target.name, "url": f"/downloads/{target.name}"})
            if parsed.path == "/api/ai-plan/validate":
                return self.send_json(validate_ai_plan(self.body()))
            if parsed.path == "/api/ai-plan/apply":
                data = self.body(); plan = data.get("plan"); selected = data.get("selected_ids", [])
                if not isinstance(plan, dict) or not isinstance(selected, list): raise ValueError("Invalid AI plan application")
                return self.send_json(apply_ai_plan(plan, selected))
            if parsed.path == "/api/tomorrow":
                data = self.body()
                return self.send_json(prepare_tomorrow(valid_day(data["source_day"]), valid_day(data["target_day"]), data.get("mission_ids", [])))
            if parsed.path == "/api/backup":
                target = verified_backup()
                return self.send_json({"ok": True, "filename": target.name})
            if parsed.path == "/api/mission":
                d = self.body(); stamp = now_iso(); fields = normalize_mission_fields(d, True)
                day = valid_day(d["day"])
                with connect() as con:
                    if fields.get("project_id") is not None and con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (fields["project_id"],)).fetchone() is None: raise ValueError("Linked project not found")
                    if fields.get("milestone_id") is not None:
                        linked = con.execute("SELECT project_id FROM milestones WHERE id=? AND active=1", (fields["milestone_id"],)).fetchone()
                        if linked is None or int(linked[0]) != int(fields.get("project_id") or 0): raise ValueError("Milestone must belong to the linked project")
                    cur = con.execute("""INSERT INTO missions(day,area,title,priority,best_time,suggested_minutes,status,result,next_action,progress_before,progress_after,score_weight,sort_order,project_id,milestone_id,success_evidence,resume_location,blocker_reason,if_then_cue,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (day,fields.get("area","orchestration"),fields["title"],fields.get("priority","important"),fields.get("best_time","Anytime"),fields.get("suggested_minutes",30),fields.get("status","not_started"),fields.get("result",""),fields.get("next_action",""),fields.get("progress_before",0),fields.get("progress_after",0),fields.get("score_weight",10),fields.get("sort_order",999),fields.get("project_id"),fields.get("milestone_id"),fields.get("success_evidence",""),fields.get("resume_location",""),fields.get("blocker_reason",""),fields.get("if_then_cue",""),stamp,stamp))
                return self.send_json({"ok": True, "id": cur.lastrowid}, 201)
            if parsed.path == "/api/project":
                fields = normalize_project_fields(self.body(), True); stamp = now_iso()
                with connect() as con:
                    cur = con.execute("INSERT INTO projects(name,area,objective,active,next_action,updated_at) VALUES(?,?,?,?,?,?)", (fields["name"], fields.get("area", "orchestration"), fields.get("objective", ""), 1, fields.get("next_action", ""), stamp))
                return self.send_json({"ok": True, "id": cur.lastrowid}, 201)
            if parsed.path == "/api/milestone":
                data = self.body(); project_id = int(data["project_id"]); fields = normalize_milestone_fields(data, True)
                with connect() as con:
                    if con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (project_id,)).fetchone() is None: raise LookupError("Project not found")
                    order = fields.get("sort_order", con.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM milestones WHERE project_id=?", (project_id,)).fetchone()[0])
                    cur = con.execute("INSERT INTO milestones(project_id,title,weight,progress,status,evidence,sort_order,active) VALUES(?,?,?,?,?,?,?,1)", (project_id, fields["title"], fields.get("weight", 10), fields.get("progress", 0), fields.get("status", "not_started"), fields.get("evidence", ""), order))
                return self.send_json({"ok": True, "id": cur.lastrowid}, 201)
            if parsed.path == "/api/notes":
                d = self.body(); day = valid_day(d["day"])
                energy_start = None if d.get("energy_start") in (None, "") else int(bounded_number(d["energy_start"], 0, 10, "energy_start"))
                energy_end = None if d.get("energy_end") in (None, "") else int(bounded_number(d["energy_end"], 0, 10, "energy_end"))
                reflection = bounded_text(d.get("reflection", ""), "reflection")
                tomorrow = bounded_text(d.get("tomorrow_focus", ""), "tomorrow_focus")
                with connect() as con:
                    con.execute("""INSERT INTO daily_notes(day,energy_start,energy_end,reflection,tomorrow_focus,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET energy_start=excluded.energy_start,energy_end=excluded.energy_end,reflection=excluded.reflection,tomorrow_focus=excluded.tomorrow_focus,updated_at=excluded.updated_at""", (day, energy_start, energy_end, reflection, tomorrow, now_iso()))
                return self.send_json({"ok": True})
            if parsed.path == "/api/study-review":
                d = self.body(); mission_id = int(d["mission_id"])
                recall = d.get("recall"); practice = d.get("practice")
                if recall not in {None, "weak", "partial", "solid"}: raise ValueError("Invalid recall result")
                if practice not in {None, "not_tested", "partial", "passed"}: raise ValueError("Invalid practice result")
                next_review = valid_day(d["next_review_day"]) if d.get("next_review_day") else None
                with connect() as con:
                    if con.execute("SELECT 1 FROM missions WHERE id=? AND active=1 AND area='study'", (mission_id,)).fetchone() is None: raise LookupError("Study mission not found")
                    con.execute("""INSERT INTO study_reviews(mission_id,recall,practice,next_review_day,updated_at) VALUES(?,?,?,?,?)
                        ON CONFLICT(mission_id) DO UPDATE SET recall=excluded.recall,practice=excluded.practice,next_review_day=excluded.next_review_day,updated_at=excluded.updated_at""",
                        (mission_id, recall, practice, next_review, now_iso()))
                return self.send_json({"ok": True})
            if parsed.path == "/api/restore":
                data = self.body(); restore_item(data["kind"], int(data["id"]))
                return self.send_json({"ok": True})
            if parsed.path == "/api/rollover":
                data = self.body(); result = rollover_mission(int(data["mission_id"]), valid_day(data["target_day"]), data.get("mode", "continue"))
                return self.send_json(result, 200 if result.get("existing") or result.get("deferred") else 201)
        except LookupError as exc:
            return self.send_json({"error": str(exc)}, 404)
        except (ValueError, KeyError, json.JSONDecodeError, sqlite3.IntegrityError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        self.send_error(404)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/mission/"):
                mid = int(parsed.path.rsplit("/", 1)[1]); fields = normalize_mission_fields(self.body())
                if not fields: return self.send_json({"error": "No valid fields"}, 400)
                with connect() as con:
                    fields = harmonize_mission_fields(con, mid, fields)
                    if fields.get("status") == "completed":
                        close_focus_sessions(con, mid)
                        fields["timer_state"] = "finished"
                    fields["updated_at"] = now_iso()
                    sql = "UPDATE missions SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
                    con.execute(sql, [*fields.values(), mid])
                return self.send_json({"ok": True})
            if parsed.path.startswith("/api/milestone/"):
                mid = int(parsed.path.rsplit("/", 1)[1]); d = self.body()
                fields = harmonize_milestone_fields(normalize_milestone_fields(d))
                if fields:
                    with connect() as con:
                        if con.execute("SELECT 1 FROM milestones WHERE id=? AND active=1", (mid,)).fetchone() is None: raise LookupError("Milestone not found")
                        fields["updated_at"] = now_iso()
                        con.execute("UPDATE milestones SET "+",".join(f"{k}=?" for k in fields)+" WHERE id=?", [*fields.values(),mid])
                return self.send_json({"ok": True})
            if parsed.path.startswith("/api/project/"):
                project_id = int(parsed.path.rsplit("/", 1)[1]); fields = normalize_project_fields(self.body())
                if not fields: return self.send_json({"error": "No valid fields"}, 400)
                fields["updated_at"] = now_iso()
                with connect() as con:
                    if con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (project_id,)).fetchone() is None: raise LookupError("Project not found")
                    con.execute("UPDATE projects SET "+",".join(f"{k}=?" for k in fields)+" WHERE id=?", [*fields.values(), project_id])
                return self.send_json({"ok": True})
        except LookupError as exc:
            return self.send_json({"error": str(exc)}, 404)
        except (ValueError, json.JSONDecodeError, sqlite3.IntegrityError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        self.send_error(404)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/mission/"):
                mission_id = int(parsed.path.rsplit("/", 1)[1])
                with TIMER_LOCK:
                    with connect() as con:
                        require_mission(con, mission_id)
                        close_focus_sessions(con, mission_id)
                        con.execute("UPDATE missions SET active=0,timer_state='finished',updated_at=? WHERE id=?", (now_iso(), mission_id))
                return self.send_json({"ok": True, "archived": True})
            if parsed.path.startswith("/api/milestone/"):
                milestone_id = int(parsed.path.rsplit("/", 1)[1])
                with connect() as con:
                    if con.execute("SELECT 1 FROM milestones WHERE id=? AND active=1", (milestone_id,)).fetchone() is None: raise LookupError("Milestone not found")
                    con.execute("UPDATE milestones SET active=0 WHERE id=?", (milestone_id,))
                return self.send_json({"ok": True, "archived": True})
            if parsed.path.startswith("/api/project/"):
                project_id = int(parsed.path.rsplit("/", 1)[1])
                with connect() as con:
                    if con.execute("SELECT 1 FROM projects WHERE id=? AND active=1", (project_id,)).fetchone() is None: raise LookupError("Project not found")
                    con.execute("UPDATE projects SET active=0,updated_at=? WHERE id=?", (now_iso(), project_id))
                return self.send_json({"ok": True, "archived": True})
        except LookupError as exc:
            return self.send_json({"error": str(exc)}, 404)
        except (ValueError, sqlite3.IntegrityError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        self.send_error(404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FORGE locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8877, help="Preferred port; FORGE safely falls back if occupied")
    parser.add_argument("--port-span", type=int, default=20, help="Number of fallback ports to try")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    ports = range(args.port, args.port + max(1, args.port_span))
    # A second shortcut click must only reopen the existing app; it must not
    # migrate the database or reinterpret its active timer as a crash.
    for port in ports:
        try:
            with urlopen(f"http://{args.host}:{port}/api/identity", timeout=0.12) as response:
                identity = json.loads(response.read())
                if identity.get("app") == "FORGE":
                    if not args.no_browser:
                        webbrowser.open(f"http://{args.host}:{port}")
                    return
        except Exception:
            pass
    # Back up the pre-migration database, then initialize and reconcile a prior crash.
    if DB_PATH.exists():
        verified_backup("forge_prestart")
    init_db()
    reconcile_interrupted_timers()
    automatic_daily_backup()
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(target=heartbeat, args=(stop_event,), daemon=True)
    heartbeat_thread.start()
    server = None
    selected_port = None
    for port in ports:
        try:
            server = ThreadingHTTPServer((args.host, port), Handler)
            selected_port = port
            break
        except OSError:
            continue
    if server is None or selected_port is None:
        raise SystemExit(f"FORGE could not find a free local port in {args.port}-{args.port + max(1, args.port_span) - 1}")
    url = f"http://{args.host}:{selected_port}"
    print(f"FORGE is running at {url}")
    print("Press Ctrl+C to stop it. Your data remains stored locally.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nFORGE stopped safely.")
    finally:
        stop_event.set()
        with connect() as con:
            closed = close_focus_sessions(con)
            for mission_id in closed:
                con.execute("UPDATE missions SET timer_state='paused',updated_at=? WHERE id=?", (now_iso(), mission_id))
        server.server_close()


if __name__ == "__main__":
    main()
