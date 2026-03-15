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


TOOL_FIELD_DEFS: Dict[str, List[Dict[str, Any]]] = {
    "web_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "What should we search for?",
        },
        {
            "key": "max_results",
            "label": "Max results",
            "type": "number",
            "default": 5,
            "help": "Number of results to return.",
        },
    ],
    "crypto_price": [
        {
            "key": "coin_id",
            "label": "Coin ID",
            "type": "text",
            "default": "bitcoin",
            "help": "CoinGecko coin id (e.g., bitcoin, ethereum).",
        },
        {
            "key": "vs_currency",
            "label": "Quote currency",
            "type": "text",
            "default": "usd",
            "help": "Currency to compare against (e.g., usd).",
        },
    ],
    "crypto_news": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "bitcoin",
            "help": "News search term.",
        },
        {
            "key": "limit",
            "label": "Max items",
            "type": "number",
            "default": 5,
            "help": "Number of news items to fetch.",
        },
    ],
    "news_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "News search term.",
        },
        {
            "key": "limit",
            "label": "Max items",
            "type": "number",
            "default": 5,
            "help": "Number of news items to fetch.",
        },
    ],
    "arxiv_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "arXiv search query.",
        },
        {
            "key": "max_results",
            "label": "Max results",
            "type": "number",
            "default": 5,
            "help": "Number of papers to return.",
        },
    ],
    "wikipedia_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "Wikipedia search term.",
        },
        {
            "key": "max_results",
            "label": "Max results",
            "type": "number",
            "default": 5,
            "help": "Number of articles to return.",
        },
    ],
    "reddit_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "Reddit search term.",
        },
        {
            "key": "limit",
            "label": "Max posts",
            "type": "number",
            "default": 10,
            "help": "Number of posts to return.",
        },
        {
            "key": "sort",
            "label": "Sort",
            "type": "text",
            "default": "new",
            "help": "Sorting (new, hot, relevance, top, comments).",
        },
    ],
    "github_search": [
        {
            "key": "query",
            "label": "Search query",
            "type": "text",
            "default": "",
            "help": "GitHub search query.",
        },
        {
            "key": "per_page",
            "label": "Max repos",
            "type": "number",
            "default": 10,
            "help": "Number of repositories to return.",
        },
        {
            "key": "sort",
            "label": "Sort",
            "type": "text",
            "default": "stars",
            "help": "Sorting (stars, forks, updated).",
        },
    ],
    "hn_top": [
        {
            "key": "limit",
            "label": "Max stories",
            "type": "number",
            "default": 10,
            "help": "Number of top stories to return.",
        },
    ],
    "rss_reader": [
        {
            "key": "url",
            "label": "RSS feed URL",
            "type": "text",
            "default": "",
            "help": "Paste the RSS feed URL.",
        },
        {
            "key": "limit",
            "label": "Max items",
            "type": "number",
            "default": 5,
            "help": "Number of items to fetch.",
        },
    ],
    "http_fetch": [
        {
            "key": "url",
            "label": "URL",
            "type": "text",
            "default": "",
            "help": "Page to fetch.",
        },
        {
            "key": "timeout",
            "label": "Timeout (seconds)",
            "type": "number",
            "default": 15,
            "help": "Request timeout.",
        },
        {
            "key": "max_chars",
            "label": "Max characters",
            "type": "number",
            "default": 5000,
            "help": "Trim long responses.",
        },
    ],
    "filesystem_read": [
        {
            "key": "path",
            "label": "File path",
            "type": "text",
            "default": "",
            "help": "Absolute path to the file.",
        },
        {
            "key": "max_chars",
            "label": "Max characters",
            "type": "number",
            "default": 5000,
            "help": "Trim long files.",
        },
    ],
    "market_sentiment": [
        {
            "key": "text",
            "label": "Text to analyze",
            "type": "text_area",
            "default": "",
            "help": "Paste the text you want analyzed.",
        }
    ],
}


SCHEDULE_PRESETS = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Hourly": "hourly",
    "Custom (advanced)": "custom",
}

WEEKDAY_OPTIONS = [
    ("Monday", 1),
    ("Tuesday", 2),
    ("Wednesday", 3),
    ("Thursday", 4),
    ("Friday", 5),
    ("Saturday", 6),
    ("Sunday", 0),
]


TEMPLATES = {
    "Blank": {
        "name": "",
        "goal": "",
        "tools": [],
        "inputs": {},
        "schedule": "0 15 * * *",
        "enabled": True,
    },
    "Bitcoin Monitor": {
        "name": "Bitcoin Monitor",
        "goal": "Determine whether to buy, hold, or pause Bitcoin purchases.",
        "tools": ["crypto_price", "crypto_news", "market_sentiment"],
        "inputs": {
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "query": "bitcoin",
            "limit": 5,
        },
        "schedule": "0 15 * * *",
        "enabled": True,
    },
}


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


def _load_tool_specs() -> Tuple[List[str], Dict[str, str], List[str]]:
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
    descriptions = {spec.name: spec.description for spec in specs}
    return names, descriptions, mcp_errors


def _coerce_value(value: str) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _infer_schedule_mode(schedule: str) -> Tuple[str, Dict[str, Any]]:
    parts = schedule.split()
    if len(parts) != 5:
        return "Custom (advanced)", {"custom": schedule}

    minute, hour, dom, month, dow = parts
    if dom == "*" and month == "*" and dow == "*":
        if hour.startswith("*/") and minute == "0":
            try:
                interval = int(hour.replace("*/", ""))
                return "Hourly", {"interval": interval}
            except ValueError:
                return "Custom (advanced)", {"custom": schedule}
        if hour.isdigit() and minute.isdigit():
            return "Daily", {"hour": int(hour), "minute": int(minute)}

    if dom == "*" and month == "*" and dow.isdigit():
        if hour.isdigit() and minute.isdigit():
            day_num = int(dow)
            day_name = next((name for name, num in WEEKDAY_OPTIONS if num == day_num), "Monday")
            return "Weekly", {"hour": int(hour), "minute": int(minute), "weekday": day_name}

    return "Custom (advanced)", {"custom": schedule}


def _set_default(key: str, value: Any) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _render_schedule_builder(prefix: str, schedule: str) -> str:
    mode_key = f"{prefix}_schedule_mode"
    custom_key = f"{prefix}_schedule_custom"
    hour_key = f"{prefix}_schedule_hour"
    minute_key = f"{prefix}_schedule_minute"
    weekday_key = f"{prefix}_schedule_weekday"
    interval_key = f"{prefix}_schedule_interval"

    _set_default(mode_key, "Custom (advanced)")
    _set_default(custom_key, schedule)
    _set_default(hour_key, 9)
    _set_default(minute_key, 0)
    _set_default(weekday_key, WEEKDAY_OPTIONS[0][0])
    _set_default(interval_key, 1)

    mode = st.selectbox("Schedule type", list(SCHEDULE_PRESETS.keys()), key=mode_key)

    if mode == "Daily":
        st.caption("Runs every day at the selected time (UTC by default).")
        hour = st.number_input("Hour (0-23)", 0, 23, key=hour_key)
        minute = st.number_input("Minute (0-59)", 0, 59, key=minute_key)
        cron = f"{minute} {hour} * * *"
    elif mode == "Weekly":
        st.caption("Runs weekly on the selected day and time.")
        day = st.selectbox("Day", [d[0] for d in WEEKDAY_OPTIONS], key=weekday_key)
        hour = st.number_input("Hour (0-23)", 0, 23, key=hour_key)
        minute = st.number_input("Minute (0-59)", 0, 59, key=minute_key)
        day_num = next(d[1] for d in WEEKDAY_OPTIONS if d[0] == day)
        cron = f"{minute} {hour} * * {day_num}"
    elif mode == "Hourly":
        st.caption("Runs every N hours.")
        interval = st.selectbox("Every", [1, 2, 3, 4, 6, 12], key=interval_key)
        cron = f"0 */{interval} * * *"
    else:
        st.caption("Advanced: edit the cron expression directly.")
        cron = st.text_input("Cron expression", key=custom_key)

    if mode != "Custom (advanced)":
        st.code(f"Cron: {cron}")
    return cron


def _build_extra_rows(inputs: Dict[str, Any], known_keys: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for key, value in inputs.items():
        if key in known_keys:
            continue
        rows.append(
            {
                "key": key,
                "value": json.dumps(value) if not isinstance(value, str) else value,
            }
        )
    return rows


def _reset_form_state(prefix: str, task_like: Dict[str, Any]) -> None:
    name_key = f"{prefix}_name"
    goal_key = f"{prefix}_goal"
    tools_key = f"{prefix}_tools_selected"
    enabled_key = f"{prefix}_enabled"

    st.session_state[name_key] = task_like.get("name", "")
    st.session_state[goal_key] = task_like.get("goal", "")
    st.session_state[tools_key] = task_like.get("tools", [])
    st.session_state[enabled_key] = task_like.get("enabled", True)

    schedule_mode, meta = _infer_schedule_mode(task_like.get("schedule", "0 15 * * *"))
    st.session_state[f"{prefix}_schedule_mode"] = schedule_mode
    st.session_state[f"{prefix}_schedule_custom"] = task_like.get("schedule", "0 15 * * *")
    st.session_state[f"{prefix}_schedule_hour"] = meta.get("hour", 9)
    st.session_state[f"{prefix}_schedule_minute"] = meta.get("minute", 0)
    st.session_state[f"{prefix}_schedule_weekday"] = meta.get("weekday", WEEKDAY_OPTIONS[0][0])
    st.session_state[f"{prefix}_schedule_interval"] = meta.get("interval", 1)

    inputs = task_like.get("inputs", {})
    tools = task_like.get("tools", [])
    known_keys = []
    for tool in tools:
        for field in TOOL_FIELD_DEFS.get(tool, []):
            key = field["key"]
            known_keys.append(key)
            st.session_state[f"{prefix}_{tool}_{key}"] = inputs.get(key, field.get("default", ""))

    # Note: data_editor values cannot be set via session_state.

def _render_tool_inputs(
    selected_tools: List[str],
    existing_inputs: Dict[str, Any],
    prefix: str,
) -> Tuple[Dict[str, Any], List[str]]:
    inputs: Dict[str, Any] = {}
    known_keys: List[str] = []

    if not selected_tools:
        st.info("Select at least one tool to configure inputs.")
        return inputs, known_keys

    for tool in selected_tools:
        tool_key = tool.split("/")[-1]
        fields = TOOL_FIELD_DEFS.get(tool_key, [])
        if not fields:
            continue
        st.subheader(f"{tool} inputs")
        for field in fields:
            key = field["key"]
            known_keys.append(key)
            widget_key = f"{prefix}_{tool}_{key}"
            default_value = existing_inputs.get(key, field.get("default", ""))
            if field["type"] == "number":
                try:
                    default_number = int(default_value)
                except (TypeError, ValueError):
                    default_number = int(field.get("default", 0))
                value = st.number_input(
                    field["label"],
                    value=default_number,
                    step=1,
                    key=widget_key,
                    help=field.get("help"),
                )
                inputs[key] = value
            elif field["type"] == "text_area":
                value = st.text_area(
                    field["label"],
                    value=str(default_value) if default_value is not None else "",
                    key=widget_key,
                    help=field.get("help"),
                )
                if value.strip():
                    inputs[key] = value.strip()
            else:
                value = st.text_input(
                    field["label"],
                    value=str(default_value) if default_value is not None else "",
                    key=widget_key,
                    help=field.get("help"),
                )
                if value.strip():
                    inputs[key] = value.strip()

    return inputs, known_keys


def _render_extra_inputs(
    existing_inputs: Dict[str, Any],
    known_keys: List[str],
    prefix: str,
    state_suffix: str,
) -> Dict[str, Any]:
    extra_rows = _build_extra_rows(existing_inputs, known_keys)

    st.caption("Add extra inputs as key/value pairs.")
    data = st.data_editor(
        extra_rows,
        num_rows="dynamic",
        key=f"{prefix}_extras_{state_suffix}",
        column_config={
            "key": st.column_config.TextColumn("Key"),
            "value": st.column_config.TextColumn("Value"),
        },
    )

    extras: Dict[str, Any] = {}
    for row in data:
        key = str(row.get("key", "")).strip()
        value = str(row.get("value", "")).strip()
        if not key:
            continue
        extras[key] = _coerce_value(value)
    return extras


def _validate_task_inputs(name: str, schedule: str, tools_selected: List[str]) -> List[str]:
    errors = []
    if not name.strip():
        errors.append("Task name is required.")
    if len(schedule.split()) < 5:
        errors.append("Schedule must be a valid 5-field cron expression.")
    if not tools_selected:
        errors.append("Select at least one tool.")
    return errors


def _build_task_payload(
    name: str,
    schedule: str,
    goal: str,
    tools_selected: List[str],
    inputs: Dict[str, Any],
    enabled: bool,
) -> TaskDefinition:
    return TaskDefinition(
        name=name.strip(),
        schedule=schedule,
        goal=goal.strip(),
        tools=tools_selected,
        inputs=inputs,
        enabled=enabled,
    )


st.title("LocalPrometheOS — Autonomous AI monitoring powered by local models.")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Tasks", "Create Task", "Edit Task", "Results", "Logs"],
)

tasks_dir = PROJECT_ROOT / "tasks"
all_tasks = load_tasks(tasks_dir)
results = db.get_last_results()

if page == "Dashboard":
    st.header("Dashboard")
    st.write("Quick view of the latest results.")
    if results:
        for row in results:
            with st.expander(f"{row['name']} (last status: {row.get('status')})"):
                st.write("Goal:", row.get("goal"))
                st.write("Schedule:", row.get("schedule"))
                st.write("Last result:")
                st.write(row.get("result_text"))
    else:
        st.info("No task runs recorded yet.")

if page == "Tasks":
    st.header("Tasks")
    if all_tasks:
        for task in all_tasks:
            with st.expander(f"{task.name}"):
                st.write("Goal:", task.goal)
                st.write("Schedule:", task.schedule)
                st.write("Tools:", ", ".join(task.tools))
                st.write("Enabled:", task.enabled)
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

if page == "Create Task":
    st.header("Create Task")
    st.write("Use the guided form below. You can use advanced options if you know cron or JSON.")

    tool_choices, tool_descriptions, mcp_errors = _load_tool_specs()
    if mcp_errors:
        st.warning("Some MCP tools could not be loaded. Built-in tools are still available.")

    selected_template = st.selectbox("Start from a template", list(TEMPLATES.keys()), key="create_template_select")
    template = TEMPLATES[selected_template]
    if "create_template" not in st.session_state:
        st.session_state.create_template = selected_template
        _reset_form_state("create", template)
    if selected_template != st.session_state.create_template:
        st.session_state.create_template = selected_template
        _reset_form_state("create", template)

    with st.form("create_task_form"):
        name = st.text_input("Task name", key="create_name")
        goal = st.text_area("Goal", key="create_goal")

        schedule = _render_schedule_builder("create", template["schedule"])

        tools_selected = st.multiselect(
            "Tools",
            options=tool_choices,
            key="create_tools_selected",
            help="Select from built-in and MCP tools.",
        )
        if tools_selected:
            st.caption("Tool descriptions")
            for tool in tools_selected:
                desc = tool_descriptions.get(tool, "")
                if desc:
                    st.write(f"- {tool}: {desc}")

        st.subheader("Inputs")
        guided_inputs, known_keys = _render_tool_inputs(
            tools_selected,
            template.get("inputs", {}),
            prefix="create",
        )
        extra_inputs = _render_extra_inputs(
            template.get("inputs", {}),
            known_keys,
            prefix="create",
            state_suffix=selected_template.replace(" ", "_").lower(),
        )
        enabled = st.checkbox("Enabled", key="create_enabled")

        submitted = st.form_submit_button("Create Task")

    if submitted:
        errors = _validate_task_inputs(name, schedule, tools_selected)
        if errors:
            for error in errors:
                st.error(error)
        else:
            inputs = {**guided_inputs, **extra_inputs}
            new_task = _build_task_payload(name, schedule, goal, tools_selected, inputs, enabled)
            save_task(new_task, tasks_dir)
            db.upsert_task(new_task)
            st.success(f"Task '{name}' created.")
            st.rerun()

if page == "Edit Task":
    st.header("Edit Task")
    if not all_tasks:
        st.info("No tasks available to edit.")
    else:
        task_names = [task.name for task in all_tasks]
        selected_name = st.selectbox("Select a task", task_names, key="edit_selected_task")
        selected_task = next(task for task in all_tasks if task.name == selected_name)

        edit_payload = {
            "name": selected_task.name,
            "goal": selected_task.goal,
            "tools": selected_task.tools,
            "inputs": selected_task.inputs,
            "schedule": selected_task.schedule,
            "enabled": selected_task.enabled,
        }
        if st.session_state.get("edit_loaded_task") != selected_task.name:
            st.session_state.edit_loaded_task = selected_task.name
            _reset_form_state("edit", edit_payload)

        tool_choices, tool_descriptions, mcp_errors = _load_tool_specs()
        if mcp_errors:
            st.warning("Some MCP tools could not be loaded. Built-in tools are still available.")

        with st.form("edit_task_form"):
            name = st.text_input("Task name", key="edit_name")
            goal = st.text_area("Goal", key="edit_goal")

            schedule = _render_schedule_builder("edit", selected_task.schedule)

            tools_selected = st.multiselect(
                "Tools",
                options=tool_choices,
                key="edit_tools_selected",
                help="Select from built-in and MCP tools.",
            )
            if tools_selected:
                st.caption("Tool descriptions")
                for tool in tools_selected:
                    desc = tool_descriptions.get(tool, "")
                    if desc:
                        st.write(f"- {tool}: {desc}")

            st.subheader("Inputs")
            guided_inputs, known_keys = _render_tool_inputs(
                tools_selected,
                selected_task.inputs,
                prefix="edit",
            )
            extra_inputs = _render_extra_inputs(
                selected_task.inputs,
                known_keys,
                prefix="edit",
                state_suffix=selected_task.name.replace(" ", "_").lower(),
            )
            enabled = st.checkbox("Enabled", key="edit_enabled")

            submitted = st.form_submit_button("Save Changes")

        if submitted:
            errors = _validate_task_inputs(name, schedule, tools_selected)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                inputs = {**guided_inputs, **extra_inputs}
                updated_task = _build_task_payload(name, schedule, goal, tools_selected, inputs, enabled)
                new_path = save_task(updated_task, tasks_dir)
                if selected_task.source_file and selected_task.source_file.exists():
                    try:
                        if selected_task.source_file != new_path:
                            selected_task.source_file.unlink()
                    except OSError:
                        st.warning("Updated task saved, but old file could not be removed.")
                db.upsert_task(updated_task)
                st.success(f"Task '{name}' updated.")
                st.rerun()

if page == "Results":
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
    else:
        st.info("No results yet.")

if page == "Logs":
    st.header("Logs")
    logs = db.get_recent_logs()
    if logs:
        st.table(logs)
    else:
        st.info("No logs yet.")
