"""Streamlit dashboard for LocalPrometheOS."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config import load_config  # noqa: E402
from database.db import Database  # noqa: E402
from models.lmstudio_client import LMStudioClient  # noqa: E402
from orchestrator.agent_controller import AgentController  # noqa: E402
from tasks.task_definition import TaskDefinition, load_tasks, save_task  # noqa: E402
from tools.builtin_tools import ToolContext, build_registry  # noqa: E402
from tools.mcp_client import MCPClient  # noqa: E402


st.set_page_config(page_title="LocalPrometheOS", layout="wide")

config = load_config()
db = Database(Path(config.storage.db_path))
db.init_db()


def _build_controller() -> AgentController:
    lm_client = LMStudioClient(
        base_url=config.lmstudio.base_url,
        model=config.lmstudio.model,
        temperature=config.lmstudio.temperature,
        max_tokens=config.lmstudio.max_tokens,
        timeout=config.lmstudio.timeout,
    )
    tool_registry = build_registry(ToolContext(lm_client=lm_client))
    if config.mcp.servers:
        mcp_client = MCPClient(config.mcp.servers)
        tool_registry.set_mcp_client(mcp_client)
    return AgentController(config=config, db=db, tool_registry=tool_registry, lm_client=lm_client)

st.title("LocalPrometheOS — Autonomous AI monitoring powered by local models.")

st.header("Dashboard")
results = db.get_last_results()
if results:
    for row in results:
        with st.expander(f"{row['name']} (last status: {row.get('status')})"):
            st.write("Goal:", row.get("goal"))
            st.write("Schedule:", row.get("schedule"))
            st.write("Last result:")
            st.write(row.get("result_text"))
else:
    st.info("No task runs recorded yet.")

st.header("Tasks")
tasks_dir = PROJECT_ROOT / "tasks"
all_tasks = load_tasks(tasks_dir)
if all_tasks:
    for task in all_tasks:
        cols = st.columns([3, 2, 2])
        with cols[0]:
            st.write(
                {
                    "name": task.name,
                    "schedule": task.schedule,
                    "enabled": task.enabled,
                    "tools": task.tools,
                    "goal": task.goal,
                }
            )
        with cols[1]:
            st.write(f"Next run: {task.schedule}")
        with cols[2]:
            if st.button("Run now", key=f"run_{task.name}"):
                controller = _build_controller()
                db.upsert_task(task)
                with st.spinner(f"Running {task.name}..."):
                    try:
                        result = controller.run_task(task)
                        st.success(f"Task {task.name} completed.")
                        st.json(result)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Task {task.name} failed: {exc}")
else:
    st.info("No tasks found.")

st.header("Create Task")
with st.form("create_task_form"):
    name = st.text_input("Name", value="")
    schedule = st.text_input("Cron schedule", value="0 15 * * *")
    goal = st.text_area("Goal", value="")
    tools = st.text_input("Tools (comma-separated)", value="crypto_price, crypto_news")
    inputs = st.text_area("Inputs (JSON)", value="{}")
    enabled = st.checkbox("Enabled", value=True)
    submitted = st.form_submit_button("Create Task")

if submitted:
    try:
        tools_list = [t.strip() for t in tools.split(",") if t.strip()]
        inputs_dict = json.loads(inputs) if inputs else {}
        new_task = TaskDefinition(
            name=name,
            schedule=schedule,
            goal=goal,
            tools=tools_list,
            inputs=inputs_dict,
            enabled=enabled,
        )
        save_task(new_task, tasks_dir)
        db.upsert_task(new_task)
        st.success(f"Task '{name}' created.")
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to create task: {exc}")

st.header("Results")
if results:
    for row in results:
        st.subheader(row["name"])
        result_json = row.get("result_json")
        if result_json:
            try:
                st.json(json.loads(result_json))
            except json.JSONDecodeError:
                st.write(result_json)
        else:
            st.write("No results yet.")

st.header("Logs")
logs = db.get_recent_logs()
if logs:
    st.table(logs)
else:
    st.info("No logs yet.")
