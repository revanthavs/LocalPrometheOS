"""SQLite persistence for LocalPrometheOS."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import sqlite3
from datetime import datetime

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
        now = datetime.utcnow().isoformat()
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
        started_at = datetime.utcnow().isoformat()
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
        finished_at = datetime.utcnow().isoformat()
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
        timestamp = datetime.utcnow().isoformat()
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

    def get_recent_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM logs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
