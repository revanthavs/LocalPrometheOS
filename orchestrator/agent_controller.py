"""Orchestrates planner, worker, and evaluator agents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
from datetime import datetime, timezone

from agents.planner_agent import PlannerAgent
from agents.worker_agent import WorkerAgent
from agents.evaluator_agent import EvaluatorAgent
from database.db import Database
from tools.builtin_tools import ToolRegistry
from config.config import AppConfig
from models.lmstudio_client import LMStudioClient


@dataclass
class AgentController:
    config: AppConfig
    db: Database
    tool_registry: ToolRegistry
    lm_client: LMStudioClient

    def run_task(self, task: Any, scheduled_for: Optional[datetime] = None) -> Dict[str, Any]:
        self.db.init_db()
        scheduled_str = scheduled_for.isoformat() if scheduled_for else None
        run_id = self.db.start_run(task.name, scheduled_str)
        planner = PlannerAgent(self.lm_client)
        worker = WorkerAgent(self.tool_registry)
        evaluator = EvaluatorAgent(self.lm_client)

        try:
            self.db.log(run_id, "INFO", f"Starting task {task.name}")
            plan = planner.create_plan(task, self.tool_registry.list_specs())
            tool_outputs = worker.execute_plan(plan, task.inputs)
            result = evaluator.summarize(task, plan, tool_outputs)

            result_text = result.get("summary", "") if isinstance(result, dict) else str(result)
            self.db.save_result(run_id, result_text, result, tool_outputs, plan)
            self._persist_result_file(task.name, run_id, result, plan, tool_outputs)
            self.db.finish_run(run_id, status="success")
            self.db.log(run_id, "INFO", f"Finished task {task.name}")
            return result
        except Exception as exc:  # noqa: BLE001
            self.db.finish_run(run_id, status="error", error=str(exc))
            self.db.log(run_id, "ERROR", f"Task {task.name} failed: {exc}")
            raise

    def _persist_result_file(
        self,
        task_name: str,
        run_id: int,
        result: Dict[str, Any],
        plan: Dict[str, Any],
        tool_outputs: Dict[str, Any],
    ) -> None:
        results_dir = Path(self.config.storage.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "task": task_name,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plan": plan,
            "tool_outputs": tool_outputs,
            "result": result,
        }
        filename = f"{task_name.replace(' ', '_').lower()}_{run_id}.json"
        (results_dir / filename).write_text(json.dumps(payload, indent=2))
