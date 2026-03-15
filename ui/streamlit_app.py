"""Streamlit dashboard for LocalPrometheOS."""
from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Any, Dict, List, Tuple

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


def _get_tool_choices() -> Tuple[List[str], List[str]]:
    tool_registry = build_registry(ToolContext())
    if config.mcp.servers:
        mcp_client = MCPClient(config.mcp.servers)
        tool_registry.set_mcp_client(mcp_client)
    mcp_errors: List[str] = []
    try:
        specs = tool_registry.list_specs()
    except Exception as exc:  # noqa: BLE001
        specs = []
        mcp_errors.append(str(exc))
    names = sorted({spec.name for spec in specs})
    return names, mcp_errors


def _parse_kv_inputs(text: str) -> Tuple[Dict[str, Any], List[str]]:
    inputs: Dict[str, Any] = {}
    errors: List[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        if "=" not in raw:
            errors.append(f"Line {idx}: expected key=value format.")
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            errors.append(f"Line {idx}: key is empty.")
            continue
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        inputs[key] = parsed_value
    return inputs, errors

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
tool_choices, mcp_errors = _get_tool_choices()
if mcp_errors:
    st.warning("Some MCP tools could not be loaded. Built-in tools are still available.")

templates = {
    "Blank": {
        "name": "",
        "goal": "",
        "tools": [],
        "inputs_kv": "",
        "inputs_json": "{}",
    },
    "Bitcoin Monitor": {
        "name": "Bitcoin Monitor",
        "goal": "Determine whether to buy, hold, or pause Bitcoin purchases.",
        "tools": ["crypto_price", "crypto_news", "market_sentiment"],
        "inputs_kv": "coin_id=bitcoin\nvs_currency=usd\nquery=bitcoin\nlimit=5",
        "inputs_json": "{}",
    },
}

if "template_applied" not in st.session_state:
    st.session_state.template_applied = "Blank"
if "task_name" not in st.session_state:
    st.session_state.task_name = ""
if "task_goal" not in st.session_state:
    st.session_state.task_goal = ""
if "task_tools" not in st.session_state:
    st.session_state.task_tools = []
if "task_inputs_kv" not in st.session_state:
    st.session_state.task_inputs_kv = ""
if "task_inputs_json" not in st.session_state:
    st.session_state.task_inputs_json = "{}"
if "schedule_value" not in st.session_state:
    st.session_state.schedule_value = "0 15 * * *"

selected_template = st.selectbox("Template", list(templates.keys()))
if selected_template != st.session_state.template_applied:
    template = templates[selected_template]
    st.session_state.task_name = template["name"]
    st.session_state.task_goal = template["goal"]
    st.session_state.task_tools = template["tools"]
    st.session_state.task_inputs_kv = template["inputs_kv"]
    st.session_state.task_inputs_json = template["inputs_json"]
    if selected_template == "Bitcoin Monitor":
        st.session_state.schedule_value = "0 15 * * *"
    st.session_state.template_applied = selected_template

schedule_presets = {
    "Daily at 15:00 UTC": "0 15 * * *",
    "Daily at 09:00 UTC": "0 9 * * *",
    "Hourly": "0 * * * *",
    "Every 6 hours": "0 */6 * * *",
    "Weekly (Mon 09:00 UTC)": "0 9 * * 1",
    "Custom": None,
}
selected_preset = st.selectbox("Schedule preset", list(schedule_presets.keys()))
if selected_preset != "Custom":
    st.session_state.schedule_value = schedule_presets[selected_preset] or st.session_state.schedule_value

with st.form("create_task_form"):
    name = st.text_input("Name", key="task_name")
    schedule = st.text_input("Cron schedule", key="schedule_value")
    goal = st.text_area("Goal", key="task_goal")
    tools_selected = st.multiselect(
        "Tools",
        options=tool_choices,
        default=st.session_state.task_tools,
        key="task_tools",
        help="Select from available built-in and MCP tools.",
    )
    st.caption("Inputs: provide key=value lines for common inputs. Use JSON override for advanced structures.")
    inputs_kv = st.text_area("Inputs (key=value per line)", key="task_inputs_kv")
    inputs_json = st.text_area("Inputs JSON override (optional)", key="task_inputs_json")
    enabled = st.checkbox("Enabled", value=True)
    submitted = st.form_submit_button("Create Task")

if submitted:
    try:
        if not name.strip():
            raise ValueError("Task name is required.")
        if len(schedule.split()) < 5:
            raise ValueError("Cron schedule must have 5 fields.")
        if not tools_selected:
            raise ValueError("Select at least one tool.")

        inputs_dict, kv_errors = _parse_kv_inputs(inputs_kv)
        if kv_errors:
            raise ValueError("; ".join(kv_errors))
        if inputs_json and inputs_json.strip() not in ("", "{}"):
            inputs_dict = json.loads(inputs_json)

        new_task = TaskDefinition(
            name=name.strip(),
            schedule=schedule,
            goal=goal,
            tools=tools_selected,
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
