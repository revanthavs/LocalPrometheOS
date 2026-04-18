"""SQLite persistence for LocalPrometheOS."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import sqlite3
from datetime import datetime, timezone

from tasks.task_definition import TaskDefinition


@dataclass
class Database:
    path: Path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    name TEXT PRIMARY KEY,
                    schedule TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    source_file TEXT,
                    last_loaded_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    scheduled_for TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    FOREIGN KEY(task_name) REFERENCES tasks(name)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_results (
                    run_id INTEGER PRIMARY KEY,
                    result_text TEXT,
                    result_json TEXT,
                    tool_outputs_json TEXT,
                    plan_json TEXT,
                    FOREIGN KEY(run_id) REFERENCES task_runs(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES task_runs(id)
                )
                """
            )

    def upsert_task(self, task: TaskDefinition) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (name, schedule, goal, tools_json, enabled, source_file, last_loaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    schedule=excluded.schedule,
                    goal=excluded.goal,
                    tools_json=excluded.tools_json,
                    enabled=excluded.enabled,
                    source_file=excluded.source_file,
                    last_loaded_at=excluded.last_loaded_at
                """,
                (
                    task.name,
                    task.schedule,
                    task.goal,
                    json.dumps(task.tools),
                    1 if task.enabled else 0,
                    str(task.source_file) if task.source_file else None,
                    now,
                ),
            )

    def start_run(self, task_name: str, scheduled_for: Optional[str]) -> int:
        started_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_runs (task_name, scheduled_for, started_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (task_name, scheduled_for, started_at, "running"),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, error: Optional[str] = None) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE task_runs
                SET finished_at = ?, status = ?, error = ?
                WHERE id = ?
                """,
                (finished_at, status, error, run_id),
            )

    def save_result(
        self,
        run_id: int,
        result_text: str,
        result_json: Dict[str, Any],
        tool_outputs: Dict[str, Any],
        plan_json: Dict[str, Any],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO task_results (run_id, result_text, result_json, tool_outputs_json, plan_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    result_text=excluded.result_text,
                    result_json=excluded.result_json,
                    tool_outputs_json=excluded.tool_outputs_json,
                    plan_json=excluded.plan_json
                """,
                (
                    run_id,
                    result_text,
                    json.dumps(result_json),
                    json.dumps(tool_outputs),
                    json.dumps(plan_json),
                ),
            )

    def log(self, run_id: Optional[int], level: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO logs (run_id, level, message, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, level, message, timestamp),
            )

    def get_last_results(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT t.name, t.schedule, t.goal, t.enabled,
                       r.finished_at, r.status, res.result_text, res.result_json
                FROM tasks t
                LEFT JOIN task_runs r ON r.task_name = t.name
                LEFT JOIN task_results res ON res.run_id = r.id
                WHERE r.id IS NULL OR r.id = (
                    SELECT r2.id FROM task_runs r2 WHERE r2.task_name = t.name
                    ORDER BY r2.started_at DESC LIMIT 1
                )
                ORDER BY t.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_logs(self, limit: int = 200, level: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            if level and level.upper() != "ALL":
                rows = conn.execute(
                    """
                    SELECT * FROM logs
                    WHERE UPPER(level) = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (level.upper(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_run_history(
        self,
        task_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            query = """
                SELECT r.id, r.task_name, r.scheduled_for, r.started_at, r.finished_at,
                       r.status, r.error, res.result_json
                FROM task_runs r
                LEFT JOIN task_results res ON res.run_id = r.id
            """
            params: List[Any] = []
            if task_name:
                query += " WHERE r.task_name = ?"
                params.append(task_name)
            query += " ORDER BY r.started_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_task_stats(self) -> Dict[str, Any]:
        with self.connect() as conn:
            total_runs_row = conn.execute("SELECT COUNT(*) as count FROM task_runs").fetchone()
            total_runs = total_runs_row["count"] if total_runs_row else 0

            success_runs_row = conn.execute(
                "SELECT COUNT(*) as count FROM task_runs WHERE status = 'success'"
            ).fetchone()
            success_runs = success_runs_row["count"] if success_runs_row else 0

            failed_runs_row = conn.execute(
                "SELECT COUNT(*) as count FROM task_runs WHERE status = 'error'"
            ).fetchone()
            failed_runs = failed_runs_row["count"] if failed_runs_row else 0

            active_tasks_row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE enabled = 1"
            ).fetchone()
            active_tasks = active_tasks_row["count"] if active_tasks_row else 0

            total_tasks_row = conn.execute("SELECT COUNT(*) as count FROM tasks").fetchone()
            total_tasks = total_tasks_row["count"] if total_tasks_row else 0

            last_run_row = conn.execute(
                "SELECT task_name, finished_at FROM task_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            last_run_task = last_run_row["task_name"] if last_run_row else None
            last_run_time = last_run_row["finished_at"] if last_run_row else None

            avg_duration_row = conn.execute("""
                SELECT AVG(
                    (julianday(finished_at) - julianday(started_at)) * 86400.0
                ) as avg_seconds
                FROM task_runs
                WHERE finished_at IS NOT NULL AND status = 'success'
            """).fetchone()
            avg_duration = avg_duration_row["avg_seconds"] if avg_duration_row and avg_duration_row["avg_seconds"] else 0

        return {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "active_tasks": active_tasks,
            "total_tasks": total_tasks,
            "last_run_task": last_run_task,
            "last_run_time": last_run_time,
            "avg_duration": avg_duration,
        }
