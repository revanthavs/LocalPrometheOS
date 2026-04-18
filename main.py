"""LocalPrometheOS CLI entrypoint."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
import time

import typer

from config.config import load_config
from models.lmstudio_client import LMStudioClient
from tools.builtin_tools import ToolContext, build_registry
from tools.mcp_client import MCPClient
from database.db import Database
from orchestrator.agent_controller import AgentController
from scheduler.task_scheduler import TaskScheduler
from tasks.task_definition import TaskDefinition, load_tasks, save_task

app = typer.Typer(help="LocalPrometheOS — Autonomous AI monitoring powered by local models.")


def _tasks_dir() -> Path:
    return Path(__file__).resolve().parent / "tasks"


def _build_controller(config_path: Optional[str] = None) -> AgentController:
    config = load_config(config_path)
    db = Database(Path(config.storage.db_path))
    lm_client = LMStudioClient(
        base_url=config.lmstudio.base_url,
        model=config.lmstudio.model,
        temperature=config.lmstudio.temperature,
        max_tokens=config.lmstudio.max_tokens,
        timeout=config.lmstudio.timeout,
    )
    project_root = Path(__file__).resolve().parent
    allowed_dirs = [
        (project_root / d).resolve()
        for d in config.filesystem.allowed_dirs
    ]
    tool_registry = build_registry(ToolContext(lm_client=lm_client, filesystem_allowed_dirs=allowed_dirs))
    if config.mcp.servers:
        mcp_client = MCPClient(config.mcp.servers)
        tool_registry.set_mcp_client(mcp_client)
    return AgentController(config=config, db=db, tool_registry=tool_registry, lm_client=lm_client)


@app.command("list-tasks")
def list_tasks(config: Optional[str] = typer.Option(None, "--config")) -> None:
    """List all task definitions."""
    tasks = load_tasks(_tasks_dir())
    if not tasks:
        typer.echo("No tasks found.")
        raise typer.Exit(code=0)
    for task in tasks:
        status = "enabled" if task.enabled else "disabled"
        typer.echo(f"{task.name} [{status}] - {task.schedule} - tools: {', '.join(task.tools)}")


@app.command("run")
def run_task(task_name: str, config: Optional[str] = typer.Option(None, "--config")) -> None:
    """Run a task immediately."""
    tasks = load_tasks(_tasks_dir())
    match = next((t for t in tasks if t.name.lower() == task_name.lower()), None)
    if not match:
        typer.echo(f"Task not found: {task_name}")
        raise typer.Exit(code=1)
    controller = _build_controller(config)
    controller.db.init_db()
    controller.db.upsert_task(match)
    result = controller.run_task(match)
    typer.echo(json.dumps(result, indent=2))


@app.command("add-task")
def add_task(
    name: str = typer.Option(..., "--name"),
    schedule: str = typer.Option(..., "--schedule"),
    goal: str = typer.Option(..., "--goal"),
    tools: str = typer.Option(..., "--tools", help="Comma-separated tool names."),
    inputs: Optional[str] = typer.Option(None, "--inputs", help="JSON string for task inputs."),
) -> None:
    """Add a new task definition."""
    tool_list = [t.strip() for t in tools.split(",") if t.strip()]
    inputs_dict = json.loads(inputs) if inputs else {}
    task = TaskDefinition(
        name=name,
        schedule=schedule,
        goal=goal,
        tools=tool_list,
        inputs=inputs_dict,
        enabled=True,
    )
    path = save_task(task, _tasks_dir())
    typer.echo(f"Task saved to {path}")


@app.command("start")
def start_scheduler(config: Optional[str] = typer.Option(None, "--config")) -> None:
    """Start the scheduler and run indefinitely."""
    controller = _build_controller(config)
    scheduler = TaskScheduler(controller.config, controller.db, controller, _tasks_dir())
    scheduler.load_and_schedule()
    scheduler.start()
    typer.echo("Scheduler started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("Scheduler stopped.")


if __name__ == "__main__":
    app()
