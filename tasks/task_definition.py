"""Task definition loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import yaml


@dataclass
class TaskDefinition:
    name: str
    schedule: str
    goal: str
    tools: List[str]
    inputs: Dict[str, Any]
    enabled: bool = True
    source_file: Path | None = None


class TaskValidationError(ValueError):
    pass


def _validate_task(data: Dict[str, Any]) -> None:
    required = ["name", "schedule", "goal", "tools"]
    for field in required:
        if field not in data:
            raise TaskValidationError(f"Task missing required field: {field}")
    if not isinstance(data["tools"], list):
        raise TaskValidationError("Task 'tools' must be a list")


def load_task_file(path: Path) -> TaskDefinition:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise TaskValidationError(f"Task file {path} must contain a mapping")
    _validate_task(data)
    return TaskDefinition(
        name=data["name"],
        schedule=data["schedule"],
        goal=data["goal"],
        tools=data["tools"],
        inputs=data.get("inputs") or {},
        enabled=bool(data.get("enabled", True)),
        source_file=path,
    )


def load_tasks(tasks_dir: Path) -> List[TaskDefinition]:
    if not tasks_dir.exists():
        return []
    tasks: List[TaskDefinition] = []
    for path in sorted(tasks_dir.glob("*.yaml")):
        tasks.append(load_task_file(path))
    for path in sorted(tasks_dir.glob("*.yml")):
        tasks.append(load_task_file(path))
    return tasks


def save_task(task: TaskDefinition, tasks_dir: Path) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    path = tasks_dir / f"{task.name.replace(' ', '_').lower()}.yaml"
    payload = {
        "name": task.name,
        "schedule": task.schedule,
        "goal": task.goal,
        "tools": task.tools,
        "inputs": task.inputs or {},
        "enabled": task.enabled,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path
