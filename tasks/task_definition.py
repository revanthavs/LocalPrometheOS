"""Task definition loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
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


def _validate_cron(schedule: str) -> None:
    from apscheduler.triggers.cron import CronTrigger
    try:
        CronTrigger.from_crontab(schedule)
    except Exception as exc:
        raise TaskValidationError(f"Invalid cron schedule '{schedule}': {exc}") from exc


def validate_task(
    data: Dict[str, Any],
    known_tools: Optional[List[str]] = None,
) -> None:
    """Validate task data dict, raising TaskValidationError on any problem.

    Parameters
    ----------
    data:
        Raw task dict (as loaded from YAML or built in UI).
    known_tools:
        If provided, every tool name in the task must appear in this list.
        Required inputs for known tools are also checked.
    """
    required_fields = ["name", "schedule", "goal", "tools"]
    for field in required_fields:
        if field not in data or not data[field]:
            raise TaskValidationError(f"Task missing required field: '{field}'")

    if not isinstance(data["tools"], list) or len(data["tools"]) == 0:
        raise TaskValidationError("Task 'tools' must be a non-empty list")

    _validate_cron(data["schedule"])

    if known_tools is not None:
        unknown = [t for t in data["tools"] if t not in known_tools]
        if unknown:
            raise TaskValidationError(
                f"Unknown tool(s): {', '.join(unknown)}. "
                f"Available: {', '.join(known_tools)}"
            )


def _validate_task(data: Dict[str, Any]) -> None:
    validate_task(data)


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
    for path in sorted(tasks_dir.glob("**/*.yaml")):
        # Skip hidden directories (like .git, .claude) and __pycache__
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        tasks.append(load_task_file(path))
    for path in sorted(tasks_dir.glob("**/*.yml")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
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
