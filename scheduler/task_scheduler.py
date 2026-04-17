"""Task scheduler using APScheduler."""
from __future__ import annotations

from datetime import datetime
import logging
import time
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.config import AppConfig
from database.db import Database
from orchestrator.agent_controller import AgentController
from tasks.task_definition import TaskDefinition, load_tasks


class TaskScheduler:
    def __init__(
        self,
        config: AppConfig,
        db: Database,
        controller: AgentController,
        tasks_dir: Path,
    ) -> None:
        self.config = config
        self.db = db
        self.controller = controller
        self.tasks_dir = tasks_dir
        self.scheduler = BackgroundScheduler(
            timezone=self._resolve_timezone(config.scheduler.timezone),
            executors={"default": {"type": "threadpool", "max_workers": config.scheduler.max_workers}},
        )

    def _resolve_timezone(self, tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name)
        except Exception as exc:
            logger.warning("Invalid timezone '%s' (%s); falling back to UTC", tz_name, exc)
            return ZoneInfo("UTC")

    def load_and_schedule(self) -> List[TaskDefinition]:
        tasks = load_tasks(self.tasks_dir)
        self.db.init_db()
        for task in tasks:
            self.db.upsert_task(task)
            if not task.enabled:
                continue
            trigger = CronTrigger.from_crontab(task.schedule, timezone=self.scheduler.timezone)
            self.scheduler.add_job(
                self._run_task,
                trigger=trigger,
                args=[task],
                id=task.name,
                replace_existing=True,
                name=task.name,
            )
        return tasks

    def _run_task(self, task: TaskDefinition) -> None:
        self.controller.run_task(task, scheduled_for=datetime.utcnow())

    def start(self) -> None:
        self.scheduler.start()

    def run_forever(self) -> None:
        self.start()
        try:
            while True:
                # Keep the scheduler alive.
                time.sleep(1)
        except KeyboardInterrupt:
            self.scheduler.shutdown()
