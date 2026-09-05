import importlib.util
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("forge_app", Path(__file__).parents[1] / "forge_app.py")
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class ForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        app.DATA = root / "data"
        app.DB_PATH = app.DATA / "forge.db"
        app.EXPORTS = root / "exports"
        app.BACKUPS = root / "backups"
        app.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_connection_context_closes_database_handle(self):
        with app.connect() as con:
            con.execute("SELECT 1").fetchone()
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")

    def test_scores_separate_outcomes_from_sustainability(self):
        payload = app.day_payload("2026-08-27")
        self.assertEqual(len(payload["missions"]), 10)
        self.assertEqual(payload["summary"]["possible"], 85)
        self.assertEqual(payload["summary"]["sustainability_possible"], 15)
        self.assertEqual(payload["summary"]["score"], 0)

    def test_frontend_ai_import_uses_backend_operation_contract(self):
        javascript = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('value="${esc(op.id)}"', javascript)
        self.assertIn("op.risk==='review'", javascript)
        self.assertNotIn("op.operation_id", javascript)

    def test_compact_frontend_has_three_views_and_no_override_layer(self):
        root = Path(__file__).parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        for view in ("today", "map", "review"):
            self.assertIn(f'data-view="{view}"', html)
        self.assertIn("AI snapshot", html)
        self.assertIn("Apply all safe", html)
        self.assertFalse((root / "static" / "v080.js").exists())
        self.assertFalse((root / "static" / "v080.css").exists())

    def test_outcome_score(self):
        payload = app.day_payload("2026-08-27")
        with app.connect() as con:
            con.execute("UPDATE missions SET status='completed' WHERE id=?", (payload["missions"][0]["id"],))
            con.execute("UPDATE missions SET status='advanced',progress_after=55 WHERE id=?", (payload["missions"][1]["id"],))
        scored = app.day_payload("2026-08-27")["summary"]
        self.assertEqual(scored["xp"], 23.8)
        self.assertEqual(scored["score"], 2.8)

    def test_project_progress_is_weighted(self):
        projects = app.projects_payload()
        azure = next(p for p in projects if p["name"] == "Azure & Intune")
        self.assertGreater(azure["completion"], 30)
        self.assertLess(azure["completion"], 45)

    def test_daily_backup_is_created_once(self):
        first = app.automatic_daily_backup()
        original_mtime = first.stat().st_mtime_ns
        second = app.automatic_daily_backup()
        self.assertEqual(first, second)
        self.assertEqual(original_mtime, second.stat().st_mtime_ns)

    def test_running_focus_timer_survives_refresh(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.start_focus_timer(mission["id"])
        started = (datetime.now(timezone.utc) - timedelta(seconds=65)).isoformat(timespec="seconds")
        with app.connect() as con:
            con.execute("UPDATE timer_sessions SET started_at=? WHERE mission_id=? AND stopped_at IS NULL", (started, mission["id"]))
        refreshed = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(refreshed["running_mode"], "focus")
        self.assertEqual(refreshed["timer_state"], "running")
        self.assertGreaterEqual(refreshed["focus_seconds"], 64)

    def test_pause_resume_finish_accumulates_time(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.start_focus_timer(mission["id"])
        with app.connect() as con:
            con.execute("UPDATE timer_sessions SET started_at=? WHERE mission_id=? AND stopped_at IS NULL", ((datetime.now(timezone.utc)-timedelta(seconds=65)).isoformat(timespec="seconds"), mission["id"]))
        app.pause_focus_timer(mission["id"])
        paused = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(paused["timer_state"], "paused")
        self.assertGreaterEqual(paused["focus_seconds"], 64)
        app.start_focus_timer(mission["id"])
        with app.connect() as con:
            con.execute("UPDATE timer_sessions SET started_at=? WHERE mission_id=? AND stopped_at IS NULL", ((datetime.now(timezone.utc)-timedelta(seconds=35)).isoformat(timespec="seconds"), mission["id"]))
        app.finish_focus_timer(mission["id"])
        finished = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(finished["timer_state"], "finished")
        self.assertGreaterEqual(finished["focus_seconds"], 99)

    def test_starting_another_timer_pauses_previous_mission(self):
        missions = app.day_payload("2026-08-27")["missions"]
        app.start_focus_timer(missions[0]["id"])
        app.start_focus_timer(missions[1]["id"])
        refreshed = app.day_payload("2026-08-27")["missions"]
        self.assertEqual(refreshed[0]["timer_state"], "paused")
        self.assertEqual(refreshed[1]["timer_state"], "running")

    def test_completed_or_deferred_mission_cannot_restart_timer(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        with app.connect() as con:
            con.execute("UPDATE missions SET status='completed' WHERE id=?", (mission["id"],))
        with self.assertRaisesRegex(ValueError, "cannot start"):
            app.start_focus_timer(mission["id"])

    def test_completing_mission_closes_running_timer(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.start_focus_timer(mission["id"])
        with app.connect() as con:
            fields = app.harmonize_mission_fields(con, mission["id"], {"status": "completed"})
            if fields.get("status") == "completed":
                app.close_focus_sessions(con, mission["id"])
                fields["timer_state"] = "finished"
            fields["updated_at"] = app.now_iso()
            con.execute("UPDATE missions SET "+",".join(f"{key}=?" for key in fields)+" WHERE id=?", [*fields.values(), mission["id"]])
        completed = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["timer_state"], "finished")
        self.assertIsNone(completed["running_mode"])

    def test_ai_completion_also_closes_running_timer(self):
        day = "2026-08-27"
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        mission = export["current_day"]["missions"][0]
        app.start_focus_timer(mission["id"])
        # Export again after the local change: stale plans must not overwrite it.
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        mission = export["current_day"]["missions"][0]
        plan = {"protocol": "forge-ai-plan", "schema_version": "1.0", "based_on_export": export["export_id"], "plan_date": day, "operations": [{"id": "complete", "action": "update_mission", "target_id": mission["id"], "changes": {"status": "completed"}}]}
        app.apply_ai_plan(plan, ["complete"])
        completed = app.day_payload(day)["missions"][0]
        self.assertEqual(completed["timer_state"], "finished")
        self.assertIsNone(completed["running_mode"])

    def test_unusually_high_daily_time_is_flagged(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.set_focus_seconds(mission["id"], 12 * 3600 + 60)
        warnings = app.day_payload("2026-08-27")["summary"]["integrity_warnings"]
        self.assertTrue(any("unusually high" in warning for warning in warnings))

    def test_handoff_contains_markdown_and_json(self):
        archive = app.export_handoff("2026-08-27")
        self.assertTrue(archive.exists())
        import zipfile
        with zipfile.ZipFile(archive) as zf:
            self.assertEqual(set(zf.namelist()), {"daily_state.json", "projects.json", "journal.md"})

    def test_missing_mission_timer_is_rejected(self):
        with self.assertRaises(LookupError):
            app.start_focus_timer(999999)
        with self.assertRaises(LookupError):
            app.pause_focus_timer(999999)
        with self.assertRaises(LookupError):
            app.finish_focus_timer(999999)

    def test_interrupted_timer_stops_at_last_heartbeat_and_can_resume(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        started = datetime.now(timezone.utc) - timedelta(hours=8)
        heartbeat = started + timedelta(minutes=12)
        app.start_focus_timer(mission["id"])
        with app.connect() as con:
            con.execute("UPDATE timer_sessions SET started_at=? WHERE mission_id=? AND stopped_at IS NULL", (started.isoformat(), mission["id"]))
            con.execute("INSERT INTO app_meta(key,value) VALUES('last_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (heartbeat.isoformat(),))
        app.reconcile_interrupted_timers()
        restored = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(restored["timer_state"], "paused")
        self.assertGreaterEqual(restored["focus_seconds"], 719)
        self.assertLess(restored["focus_seconds"], 725)
        app.start_focus_timer(mission["id"])
        self.assertEqual(app.day_payload("2026-08-27")["missions"][0]["timer_state"], "running")

    def test_verified_backup_contains_latest_wal_data(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        with app.connect() as con:
            con.execute("UPDATE missions SET result='latest write' WHERE id=?", (mission["id"],))
        target = app.verified_backup("test")
        with closing(sqlite3.connect(target)) as con:
            self.assertEqual(con.execute("SELECT result FROM missions WHERE id=?", (mission["id"],)).fetchone()[0], "latest write")
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_mission_validation(self):
        valid = app.normalize_mission_fields({"title": "Custom outcome"}, creating=True)
        self.assertEqual(valid["title"], "Custom outcome")
        with self.assertRaises(ValueError): app.normalize_mission_fields({"title": "", "score_weight": -1}, creating=True)
        with self.assertRaises(ValueError): app.normalize_mission_fields({"status": "invented"})
        with self.assertRaises(ValueError): app.valid_day("not-a-date")

    def test_daily_notes_are_saved_in_handoff(self):
        day = "2026-08-27"
        with app.connect() as con:
            con.execute("INSERT INTO daily_notes(day,energy_start,energy_end,reflection,tomorrow_focus,updated_at) VALUES(?,?,?,?,?,?)", (day, 8, 5, "Good progress", "First task", app.now_iso()))
        archive = app.export_handoff(day)
        import zipfile
        with zipfile.ZipFile(archive) as zf:
            journal = zf.read("journal.md").decode()
        self.assertIn("Energy:** 8 → 5", journal)
        self.assertIn("Good progress", journal)

    def test_single_json_handoff_has_stable_protocol_and_ids(self):
        day = "2026-08-27"
        target = app.export_json_handoff(day)
        document = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(document["protocol"], "forge-snapshot")
        self.assertEqual(document["schema_version"], "2.0")
        self.assertEqual(document["date"], day)
        self.assertTrue(document["current_day"]["missions"])
        self.assertTrue(document["projects"])
        with app.connect() as con:
            self.assertEqual(con.execute("SELECT value FROM app_meta WHERE key='last_export_id'").fetchone()[0], document["export_id"])

    def test_ai_plan_is_previewed_and_applies_only_selected_operations(self):
        day = "2026-08-27"
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        mission = export["current_day"]["missions"][0]
        project = export["projects"][0]
        plan = {"protocol": "forge-ai-plan", "schema_version": "1.0", "based_on_export": export["export_id"], "plan_date": day, "warnings": [], "operations": [
            {"id": "mission-next", "action": "update_mission", "target_id": mission["id"], "changes": {"next_action": "Open the exact lab panel"}, "reason": "Make resumption concrete"},
            {"id": "project-next", "action": "update_project", "target_id": project["id"], "changes": {"next_action": "Validate the next keystone"}},
        ]}
        preview = app.validate_ai_plan(plan)
        self.assertEqual(len(preview["operations"]), 2)
        result = app.apply_ai_plan(plan, ["mission-next"])
        self.assertEqual(result["applied"], 1)
        refreshed = app.day_payload(day)["missions"][0]
        self.assertEqual(refreshed["next_action"], "Open the exact lab panel")
        self.assertNotEqual(app.projects_payload()[0]["next_action"], "Validate the next keystone")
        self.assertTrue((app.BACKUPS / result["backup"]).exists())

    def test_ai_plan_marks_milestone_regressions_for_review(self):
        milestone = app.projects_payload()[0]["milestones"][0]
        plan = {"protocol": "forge-ai-plan", "schema_version": "1.0", "plan_date": "2026-08-27", "operations": [{"id": "lower", "action": "update_milestone", "target_id": milestone["id"], "changes": {"progress": 0}}]}
        operation = app.validate_ai_plan(plan)["operations"][0]
        self.assertEqual(operation["risk"], "review")
        self.assertFalse(operation["default_selected"])

    def test_ai_plan_rejects_unknown_protocol_and_targets(self):
        with self.assertRaises(ValueError):
            app.validate_ai_plan({"protocol": "something-else", "schema_version": "1.0"})
        with self.assertRaises(ValueError):
            app.validate_ai_plan({"protocol": "forge-ai-plan", "schema_version": "1.0", "operations": [{"id": "bad", "action": "update_project", "target_id": 999999, "changes": {"next_action": "No"}}]})

    def test_prepare_tomorrow_carries_only_selected_unfinished_work(self):
        day = "2026-08-27"; tomorrow = "2026-08-28"
        missions = app.day_payload(day)["missions"]
        result = app.prepare_tomorrow(day, tomorrow, [missions[0]["id"], missions[1]["id"]])
        self.assertEqual(result["prepared"], 2)
        carried = app.day_payload(tomorrow)["missions"]
        self.assertTrue(any(m["title"] == missions[0]["title"] for m in carried))
        with self.assertRaises(ValueError): app.prepare_tomorrow(day, day, [missions[0]["id"]])

    def test_manual_time_correction_preserves_timer_history(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.start_focus_timer(mission["id"])
        with app.connect() as con:
            con.execute("UPDATE timer_sessions SET started_at=? WHERE mission_id=? AND stopped_at IS NULL", ((datetime.now(timezone.utc) - timedelta(seconds=70)).isoformat(), mission["id"]))
        result = app.set_focus_seconds(mission["id"], 1800)
        self.assertEqual(result["focus_seconds"], 1800)
        refreshed = app.day_payload("2026-08-27")["missions"][0]
        self.assertEqual(refreshed["timer_state"], "running")
        self.assertEqual(refreshed["focus_seconds"], 1800)
        with app.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM timer_sessions WHERE mission_id=?", (mission["id"],)).fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM time_adjustments WHERE mission_id=?", (mission["id"],)).fetchone()[0], 1)

    def test_manual_time_can_be_corrected_down_to_zero(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.set_focus_seconds(mission["id"], 3600)
        app.set_focus_seconds(mission["id"], 0)
        self.assertEqual(app.day_payload("2026-08-27")["missions"][0]["focus_seconds"], 0)

    def test_dashboard_aggregates_time_outcomes_and_keystones(self):
        day = "2026-08-27"
        missions = app.day_payload(day)["missions"]
        app.set_focus_seconds(missions[0]["id"], 2700)
        with app.connect() as con:
            con.execute("UPDATE missions SET status='completed' WHERE id=?", (missions[0]["id"],))
        dashboard = app.dashboard_payload(day)
        self.assertEqual(dashboard["summary"]["focus_seconds"], 2700)
        self.assertEqual(dashboard["summary"]["keystones_advanced"], 1)
        self.assertEqual(len(dashboard["days"]), 7)
        self.assertTrue(any(area["area"] == "study" and area["focus_seconds"] == 2700 for area in dashboard["areas"]))
        self.assertTrue(dashboard["projects"])

    def test_manual_time_validation(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        with self.assertRaises(ValueError): app.set_focus_seconds(mission["id"], -1)
        with self.assertRaises(ValueError): app.set_focus_seconds(mission["id"], 604801)

    def test_all_user_owned_mission_fields_are_editable(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        fields = app.normalize_mission_fields({"title": "Edited mission", "area": "veridra", "priority": "parallel", "best_time": "Flexible", "suggested_minutes": 75, "status": "advanced", "result": "Evidence", "next_action": "Continue", "progress_after": 42, "score_weight": 17})
        with app.connect() as con:
            fields["updated_at"] = app.now_iso()
            con.execute("UPDATE missions SET "+",".join(f"{key}=?" for key in fields)+" WHERE id=?", [*fields.values(), mission["id"]])
        edited = next(m for m in app.day_payload("2026-08-27")["missions"] if m["id"] == mission["id"])
        self.assertEqual((edited["title"], edited["area"], edited["priority"], edited["progress_after"], edited["score_weight"]), ("Edited mission", "veridra", "parallel", 42, 17))

    def test_advanced_editor_exposes_all_user_owned_fields(self):
        javascript = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        mission_fields = {"title", "priority", "best_time", "suggested_minutes", "status", "result",
                          "next_action", "progress_before", "progress_after", "score_weight", "sort_order",
                          "area", "project_id", "milestone_id", "success_evidence", "resume_location",
                          "blocker_reason", "blocker_active", "if_then_cue"}
        project_fields = {"name", "area", "objective", "next_action", "priority_rank"}
        milestone_fields = {"title", "weight", "progress", "status", "evidence", "sort_order",
                            "confidence", "completion_conditions"}
        for field in mission_fields | project_fields | milestone_fields:
            self.assertIn(f'data-field="{field}"', javascript)
        self.assertNotIn('data-field="active"', javascript)  # Archive/restore owns lifecycle state.

    def test_identity_is_bound_to_exact_installation_root(self):
        source = Path(app.__file__).read_text(encoding="utf-8")
        self.assertIn('"root": str(ROOT)', source)
        self.assertIn('Path(identity_root).resolve() == ROOT', source)

    def test_windows_acceptance_script_is_in_release(self):
        build_source = (Path(__file__).parents[1] / "tools" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"Test-FORGE-Windows.ps1"', build_source)
        acceptance = (Path(__file__).parents[1] / "Test-FORGE-Windows.ps1").read_text(encoding="utf-8")
        for evidence in ("Clean isolated installation", "Seed preservation marker", "Verified backup", "Forced failed upgrade"):
            self.assertIn(evidence, acceptance)

    def test_project_and_milestone_fields_are_editable(self):
        project = app.projects_payload()[0]; milestone = project["milestones"][0]
        project_fields = app.normalize_project_fields({"name": "Edited project", "area": "webify", "objective": "Edited objective", "next_action": "Edited action"})
        milestone_fields = app.normalize_milestone_fields({"title": "Edited milestone", "weight": 30, "progress": 65, "status": "advanced", "evidence": "Validated"})
        with app.connect() as con:
            project_fields["updated_at"] = app.now_iso()
            con.execute("UPDATE projects SET "+",".join(f"{key}=?" for key in project_fields)+" WHERE id=?", [*project_fields.values(), project["id"]])
            con.execute("UPDATE milestones SET "+",".join(f"{key}=?" for key in milestone_fields)+" WHERE id=?", [*milestone_fields.values(), milestone["id"]])
        edited = next(p for p in app.projects_payload() if p["id"] == project["id"])
        self.assertEqual(edited["name"], "Edited project")
        self.assertEqual(edited["milestones"][0]["evidence"], "Validated")

    def test_archiving_preserves_history_but_hides_records(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.set_focus_seconds(mission["id"], 600)
        with app.connect() as con:
            con.execute("UPDATE missions SET active=0 WHERE id=?", (mission["id"],))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM time_adjustments WHERE mission_id=?", (mission["id"],)).fetchone()[0], 1)
        self.assertFalse(any(m["id"] == mission["id"] for m in app.day_payload("2026-08-27")["missions"]))

    def test_archiving_whole_day_does_not_reseed_defaults(self):
        day = "2026-08-27"
        app.day_payload(day)
        with app.connect() as con:
            con.execute("UPDATE missions SET active=0 WHERE day=?", (day,))
        self.assertEqual(app.day_payload(day)["missions"], [])

    def test_status_and_progress_stay_consistent(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        with app.connect() as con:
            fields = app.harmonize_mission_fields(con, mission["id"], {"status": "completed"})
            self.assertEqual(fields["progress_after"], 100)
            fields = app.harmonize_mission_fields(con, mission["id"], {"progress_after": 38})
            self.assertEqual(fields["status"], "advanced")

    def test_project_and_milestone_link_validation(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        projects = app.projects_payload()
        with app.connect() as con:
            linked = app.harmonize_mission_fields(con, mission["id"], {"project_id": projects[0]["id"], "milestone_id": projects[0]["milestones"][0]["id"]})
            self.assertEqual(linked["project_id"], projects[0]["id"])
            with self.assertRaises(ValueError):
                app.harmonize_mission_fields(con, mission["id"], {"project_id": projects[0]["id"], "milestone_id": projects[1]["milestones"][0]["id"]})

    def test_dashboard_exposes_planning_energy_and_neglected_projects(self):
        day = "2026-08-27"
        mission = app.day_payload(day)["missions"][0]
        app.set_focus_seconds(mission["id"], 1800)
        with app.connect() as con:
            con.execute("UPDATE missions SET status='advanced',progress_after=50 WHERE id=?", (mission["id"],))
            con.execute("INSERT INTO daily_notes(day,energy_start,energy_end,updated_at) VALUES(?,?,?,?)", (day, 8, 5, app.now_iso()))
        dashboard = app.dashboard_payload(day)
        self.assertGreater(dashboard["summary"]["planned_minutes"], 0)
        self.assertGreater(dashboard["summary"]["time_fit"], 0)
        self.assertIn("time_variance_minutes", dashboard["summary"])
        self.assertEqual(dashboard["energy"][0]["label"], "Thu")
        self.assertFalse(dashboard["neglected_projects"])

    def test_planned_time_includes_untouched_planned_missions(self):
        dashboard = app.dashboard_payload("2026-08-27")
        expected = sum(m["suggested_minutes"] for m in app.day_payload("2026-08-27")["missions"])
        self.assertEqual(dashboard["summary"]["planned_minutes"], expected)

    def test_default_project_work_is_linked_automatically(self):
        missions = app.day_payload("2026-08-27")["missions"]
        project_areas = {"study", "employment", "jolt", "veridra", "webify", "youtube"}
        self.assertTrue(all(m["project_id"] and m["milestone_id"] for m in missions if m["area"] in project_areas))

    def test_ai_plan_cannot_apply_same_operation_twice(self):
        day = "2026-08-27"
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        plan = {"protocol": "forge-ai-plan", "schema_version": "1.0", "based_on_export": export["export_id"],
                "plan_date": day, "operations": [{"id": "add-once", "action": "create_mission",
                "data": {"day": day, "title": "Unique imported work"}}]}
        app.apply_ai_plan(plan, ["add-once"])
        with self.assertRaisesRegex(ValueError, "already applied"):
            app.apply_ai_plan(plan, ["add-once"])
        self.assertEqual(sum(m["title"] == "Unique imported work" for m in app.day_payload(day)["missions"]), 1)

    def test_stale_ai_plan_is_rejected(self):
        day = "2026-08-27"
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        mission = export["current_day"]["missions"][0]
        with app.connect() as con:
            con.execute("UPDATE missions SET result='newer local work',updated_at=? WHERE id=?", (app.now_iso(), mission["id"]))
        plan = {"protocol": "forge-ai-plan", "schema_version": "1.0", "based_on_export": export["export_id"],
                "plan_date": day, "operations": [{"id": "stale", "action": "update_mission",
                "target_id": mission["id"], "changes": {"result": "old AI work"}}]}
        with self.assertRaisesRegex(ValueError, "changed after export"):
            app.apply_ai_plan(plan, ["stale"])

    def test_milestone_status_and_progress_are_harmonized(self):
        self.assertEqual(app.harmonize_milestone_fields({"status": "completed", "progress": 40}), {"status": "advanced", "progress": 40})
        self.assertEqual(app.harmonize_milestone_fields({"status": "completed"})["progress"], 100)

    def test_completion_resolves_active_blocker_atomically(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        with app.connect() as con:
            con.execute("UPDATE missions SET blocker_reason='No test device',blocker_active=1 WHERE id=?", (mission["id"],))
        with self.assertRaisesRegex(ValueError, "active blocker"):
            app.complete_mission(mission["id"])
        app.complete_mission(mission["id"], resolve_blocker=True)
        completed = next(m for m in app.day_payload("2026-08-27")["missions"] if m["id"] == mission["id"])
        self.assertEqual((completed["status"], completed["blocker_reason"], completed["blocker_active"]), ("completed", "No test device", 0))

    def test_energy_can_remain_unknown(self):
        self.assertIsNone(app.day_payload("2026-08-27")["note"])

    def test_wip_counts_started_human_work_not_the_whole_plan(self):
        day = "2026-08-27"
        missions = app.day_payload(day)["missions"]
        self.assertEqual(app.day_payload(day)["summary"]["human_wip"], 0)
        with app.connect() as con:
            con.execute("UPDATE missions SET status='advanced',progress_after=25 WHERE id=?", (missions[0]["id"],))
            con.execute("UPDATE missions SET status='advanced',progress_after=25 WHERE id=?", (missions[6]["id"],))
        # JOLT is parallel/background; only the started human-focus mission counts.
        self.assertEqual(app.day_payload(day)["summary"]["human_wip"], 1)

    def test_rollover_replace_is_compact_and_idempotent(self):
        source_day, target_day = "2026-08-27", "2026-08-28"
        source = app.day_payload(source_day)["missions"][0]
        with app.connect() as con:
            con.execute("UPDATE missions SET next_action='Resume exact lab step' WHERE id=?", (source["id"],))
        result = app.rollover_mission(source["id"], target_day, "replace")
        self.assertIsNotNone(result["replaced"])
        target = app.day_payload(target_day)["missions"]
        self.assertEqual(len(target), 10)
        continued = next(m for m in target if m["rollover_from_id"] == source["id"])
        self.assertEqual(continued["title"], "Resume exact lab step")
        again = app.rollover_mission(source["id"], target_day, "replace")
        self.assertTrue(again["existing"])
        self.assertEqual(len(app.day_payload(target_day)["missions"]), 10)

    def test_defer_closes_running_timer(self):
        mission = app.day_payload("2026-08-27")["missions"][0]
        app.start_focus_timer(mission["id"])
        result = app.rollover_mission(mission["id"], "2026-08-28", "defer")
        self.assertTrue(result["deferred"])
        deferred = next(m for m in app.day_payload("2026-08-27")["missions"] if m["id"] == mission["id"])
        self.assertEqual((deferred["status"], deferred["timer_state"]), ("deferred", "finished"))

    def test_restoring_milestone_restores_parent_project(self):
        project = app.projects_payload()[0]
        milestone = project["milestones"][0]
        with app.connect() as con:
            con.execute("UPDATE projects SET active=0 WHERE id=?", (project["id"],))
            con.execute("UPDATE milestones SET active=0 WHERE id=?", (milestone["id"],))
        app.restore_item("milestone", milestone["id"])
        restored = next(p for p in app.projects_payload() if p["id"] == project["id"])
        self.assertTrue(any(m["id"] == milestone["id"] for m in restored["milestones"]))

    def test_snapshot_is_self_describing_and_bounded(self):
        document = json.loads(app.export_json_handoff("2026-08-27").read_text(encoding="utf-8"))
        self.assertEqual(document["planning_constraints"]["planning_owner"], "ChatGPT")
        self.assertEqual(document["return_contract"]["schema_version"], "2.0")
        self.assertTrue(document["chatgpt_instructions"])
        self.assertLessEqual(len(document["history"]["detailed_days"]), 14)

    def test_ai_project_control_bootstrap_is_complete(self):
        root = Path(__file__).parents[1]
        required = ["CONTEXT.md", "PROJECT_STATE.json", "ROADMAP.md", "ARCHITECTURE.md",
                    "DECISIONS.md", "REJECTED_APPROACHES.md", "KNOWN_ISSUES.md",
                    "OPERABILITY.md", "TEST_STATUS.json", "FILE_MAP.md", "SESSION_PROTOCOL.md"]
        self.assertTrue(all((root / ".ai" / name).exists() for name in required))
        state = json.loads((root / ".ai" / "PROJECT_STATE.json").read_text(encoding="utf-8"))
        self.assertEqual(state["git"]["is_repository"], (root / ".git").is_dir())
        self.assertEqual(state["git"]["branch"], "main")
        self.assertFalse(state["readiness"]["internal_testing_ready"])
        self.assertTrue((root / "tools" / "build_ai_context.py").exists())

    def test_v2_plan_records_decision_and_study_review(self):
        day = "2026-08-27"
        export = json.loads(app.export_json_handoff(day).read_text(encoding="utf-8"))
        study = next(m for m in export["current_day"]["missions"] if m["area"] == "study")
        plan = {"protocol": "forge-ai-plan", "schema_version": "2.0", "based_on_export": export["export_id"], "plan_date": day, "operations": [
            {"id": "decision", "action": "add_decision", "data": {"decision": "Study first", "reason": "Morning energy"}},
            {"id": "review", "action": "update_study_review", "target_id": study["id"], "changes": {"recall": "solid", "practice": "passed", "next_review_day": "2026-08-30"}},
        ]}
        app.apply_ai_plan(plan, ["decision", "review"])
        dashboard = app.dashboard_payload(day)
        self.assertEqual(dashboard["decisions"][0]["decision"], "Study first")
        with app.connect() as con:
            review = con.execute("SELECT * FROM study_reviews WHERE mission_id=?", (study["id"],)).fetchone()
        self.assertEqual((review["recall"], review["practice"]), ("solid", "passed"))

    def test_milestone_confidence_and_conditions_are_validated(self):
        fields = app.normalize_milestone_fields({"confidence": "high", "completion_conditions": "Pass live validation"})
        self.assertEqual(fields["confidence"], "high")
        with self.assertRaises(ValueError):
            app.normalize_milestone_fields({"confidence": "guess"})


if __name__ == "__main__":
    unittest.main()
