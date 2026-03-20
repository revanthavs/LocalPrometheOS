"""Create Task page — step-by-step wizard."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import get_project_root, get_config, get_db
from tasks.task_definition import TaskDefinition, save_task
from ui.components.system_panel import render_system_panel


TOOL_FIELD_DEFS: Dict[str, List[Dict[str, Any]]] = {
    "web_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "max_results", "label": "Max results", "type": "number", "default": 5},
    ],
    "crypto_price": [
        {"key": "coin_id", "label": "Coin ID", "type": "text", "default": "bitcoin"},
        {"key": "vs_currency", "label": "Quote currency", "type": "text", "default": "usd"},
    ],
    "crypto_news": [
        {"key": "query", "label": "Search query", "type": "text", "default": "bitcoin"},
        {"key": "limit", "label": "Max items", "type": "number", "default": 5},
    ],
    "news_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "limit", "label": "Max items", "type": "number", "default": 5},
    ],
    "arxiv_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "max_results", "label": "Max results", "type": "number", "default": 5},
    ],
    "wikipedia_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "max_results", "label": "Max results", "type": "number", "default": 5},
    ],
    "reddit_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "limit", "label": "Max posts", "type": "number", "default": 10},
    ],
    "github_search": [
        {"key": "query", "label": "Search query", "type": "text", "default": ""},
        {"key": "per_page", "label": "Max repos", "type": "number", "default": 10},
    ],
    "hn_top": [{"key": "limit", "label": "Max stories", "type": "number", "default": 10}],
    "rss_reader": [
        {"key": "url", "label": "RSS feed URL", "type": "text", "default": ""},
        {"key": "limit", "label": "Max items", "type": "number", "default": 5},
    ],
    "http_fetch": [
        {"key": "url", "label": "URL", "type": "text", "default": ""},
        {"key": "timeout", "label": "Timeout (seconds)", "type": "number", "default": 15},
        {"key": "max_chars", "label": "Max characters", "type": "number", "default": 5000},
    ],
    "filesystem_read": [
        {"key": "path", "label": "File path", "type": "text", "default": ""},
        {"key": "max_chars", "label": "Max characters", "type": "number", "default": 5000},
    ],
    "market_sentiment": [
        {"key": "text", "label": "Text to analyze", "type": "text_area", "default": ""},
    ],
}

TOOL_CATEGORIES = {
    "🔍 Search": ["web_search", "news_search", "reddit_search", "github_search", "hn_top", "wikipedia_search", "arxiv_search"],
    "💰 Crypto": ["crypto_price", "crypto_news"],
    "📡 Data": ["rss_reader", "http_fetch", "filesystem_read"],
    "🧠 Analysis": ["market_sentiment"],
}

TEMPLATES = {
    "Blank": {
        "name": "", "goal": "", "tools": [], "inputs": {}, "schedule": "0 9 * * *", "enabled": True,
    },
    "Bitcoin Monitor": {
        "name": "Bitcoin Monitor",
        "goal": "Determine whether to buy, hold, or pause Bitcoin purchases.",
        "tools": ["crypto_price", "crypto_news", "market_sentiment"],
        "inputs": {"coin_id": "bitcoin", "vs_currency": "usd", "query": "bitcoin", "limit": 5},
        "schedule": "0 9 * * *",
        "enabled": True,
    },
    "AI News Monitor": {
        "name": "AI News Monitor",
        "goal": "Summarize the most important AI news and identify emerging trends.",
        "tools": ["news_search", "http_fetch", "market_sentiment"],
        "inputs": {"query": "artificial intelligence", "limit": 5},
        "schedule": "0 8 * * *",
        "enabled": True,
    },
    "Hacker News Daily": {
        "name": "Hacker News Daily",
        "goal": "Get the top stories from Hacker News and summarize key discussions.",
        "tools": ["hn_top", "http_fetch"],
        "inputs": {"limit": 10},
        "schedule": "0 10 * * *",
        "enabled": True,
    },
}

SCHEDULE_MODES = {
    "daily": {"label": "Daily", "icon": "📅", "desc": "Once a day"},
    "weekly": {"label": "Weekly", "icon": "📆", "desc": "Once a week"},
    "hourly": {"label": "Hourly", "icon": "⏰", "desc": "Every N hours"},
    "custom": {"label": "Custom", "icon": "⚙️", "desc": "Cron expression"},
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

WEEKDAY_MAP = {name: i for i, name in enumerate(WEEKDAYS)}


def _build_cron(mode: str, hour: int, minute: int, weekday: str = "Monday", interval: int = 1, custom: str = "") -> str:
    if mode == "daily":
        return f"{minute} {hour} * * *"
    elif mode == "weekly":
        dow = WEEKDAY_MAP.get(weekday, 1)
        return f"{minute} {hour} * * {dow}"
    elif mode == "hourly":
        return f"0 */{interval} * * *"
    else:
        return custom


def _cron_to_human(cron: str) -> str:
    parts = cron.split()
    if len(parts) != 5:
        return cron
    minute, hour, dom, month, dow = parts
    if dom == "*" and month == "*" and dow == "*":
        if hour.startswith("*/"):
            return f"Every {hour.replace('*/', '')} hours"
        if hour.isdigit() and minute.isdigit():
            h, m = int(hour), int(minute)
            period = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            return f"Daily at {h12}:{m:02d} {period}"
    if dom == "*" and month == "*" and dow.isdigit():
        day_name = WEEKDAYS[int(dow)] if int(dow) < 7 else dow
        h, m = int(hour), int(minute)
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{day_name} at {h12}:{m:02d} {period}"
    return cron


def _init_wizard_state():
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0
        st.session_state.wizard_data = {
            "template": "Blank",
            "name": "",
            "goal": "",
            "tools": [],
            "inputs": {},
            "schedule_mode": "daily",
            "schedule_hour": 9,
            "schedule_minute": 0,
            "schedule_weekday": "Monday",
            "schedule_interval": 1,
            "schedule_custom": "0 9 * * *",
            "enabled": True,
            "extra_inputs": {},
        }


def _render_progress(step: int, total: int = 4) -> None:
    labels = ["Basics", "Schedule", "Tools", "Review"]
    cols = st.columns([*([1] * (total * 2 - 1))])
    label_cols = st.columns(total)

    for i in range(total):
        with label_cols[i]:
            if i < step:
                color = "var(--accent)"
                label_color = "var(--text-primary)"
                circle_class = "wizard-step-done"
                label_text = f"✓ {labels[i]}"
            elif i == step:
                color = "var(--accent)"
                label_color = "var(--accent)"
                circle_class = "wizard-step-active"
                label_text = f"● {labels[i]}"
            else:
                color = "var(--border)"
                label_color = "var(--text-muted)"
                circle_class = "wizard-step-pending"
                label_text = f"○ {labels[i]}"

            st.markdown(f"""
<div style="text-align:center;">
    <div class="wizard-step-circle {circle_class}">{i + 1}</div>
    <div style="font-size:11px;color:{label_color};font-weight:500;margin-top:4px;white-space:nowrap;">{label_text}</div>
</div>
""", unsafe_allow_html=True)

        if i < total - 1:
            connector_color = "var(--accent)" if i < step else "var(--border)"
            with cols[i * 2]:
                st.markdown(f"""
<div style="height:2px;background:{connector_color};margin-top:14px;border-radius:1px;"></div>
""", unsafe_allow_html=True)


def _render_step_basics() -> bool:
    """Render Step 1: Basics. Returns True if valid."""
    st.markdown("#### Step 1: Task Basics")
    st.markdown("Give your task a name and describe what it should do.")

    data = st.session_state.wizard_data
    template = st.selectbox(
        "Start from template",
        options=list(TEMPLATES.keys()),
        index=list(TEMPLATES.keys()).index(data.get("template", "Blank")),
        help="Choose a pre-built template or start blank.",
    )
    data["template"] = template

    if template != "Blank" and st.session_state.get("_prev_template") != template:
        tpl = TEMPLATES[template]
        data["name"] = tpl.get("name", "")
        data["goal"] = tpl.get("goal", "")
        data["tools"] = tpl.get("tools", [])
        data["inputs"] = dict(tpl.get("inputs", {}))
        data["schedule_mode"] = "daily"
        st.session_state._prev_template = template

    name = st.text_input(
        "Task name *",
        value=data.get("name", ""),
        placeholder="e.g., Bitcoin Morning Check",
        help="A unique name for this task.",
    )
    data["name"] = name

    goal = st.text_area(
        "Goal *",
        value=data.get("goal", ""),
        placeholder="Describe what this task should accomplish...",
        help="The objective the AI agents will work toward.",
        height=120,
    )
    data["goal"] = goal

    enabled = st.toggle("Task enabled", value=data.get("enabled", True), help="Disabled tasks won't run on schedule.")
    data["enabled"] = enabled

    errors = []
    if name and len(name) < 2:
        errors.append("Task name must be at least 2 characters.")
    if goal and len(goal) < 10:
        errors.append("Goal should be at least 10 characters.")

    if errors:
        for e in errors:
            st.warning(e)

    return len(errors) == 0


def _render_step_schedule() -> bool:
    """Render Step 2: Schedule."""
    st.markdown("#### Step 2: Schedule")
    st.markdown("Choose how often this task should run automatically.")

    data = st.session_state.wizard_data
    mode = data.get("schedule_mode", "daily")

    # Mode selector as cards
    mode_options = list(SCHEDULE_MODES.keys())
    mode_labels = {k: f"{v['icon']} {v['label']}\n{v['desc']}" for k, v in SCHEDULE_MODES.items()}

    # Render as large button cards using columns
    card_cols = st.columns(4)
    selected_mode = mode
    for i, (m, v) in enumerate(SCHEDULE_MODES.items()):
        with card_cols[i]:
            bg = "var(--accent-dim)" if mode == m else "var(--bg-tertiary)"
            border = "2px solid var(--accent)" if mode == m else "2px solid var(--border)"
            if st.button(
                f"**{v['icon']} {v['label']}**\n{v['desc']}",
                key=f"mode_{m}",
                use_container_width=True,
            ):
                selected_mode = m
                data["schedule_mode"] = m

    mode = selected_mode
    data["schedule_mode"] = mode

    st.markdown("")

    # Time inputs based on mode
    if mode in ("daily", "weekly"):
        col_h, col_m = st.columns([1, 1])
        with col_h:
            hour = st.number_input("Hour (0-23)", 0, 23, int(data.get("schedule_hour", 9)), key="wiz_hour")
        with col_m:
            minute = st.number_input("Minute (0-59)", 0, 59, int(data.get("schedule_minute", 0)), key="wiz_minute")
        data["schedule_hour"] = hour
        data["schedule_minute"] = minute

    if mode == "weekly":
        weekday = st.selectbox("Day of week", WEEKDAYS, index=WEEKDAYS.index(data.get("schedule_weekday", "Monday")), key="wiz_weekday")
        data["schedule_weekday"] = weekday

    if mode == "hourly":
        interval = st.selectbox("Run every", [1, 2, 3, 4, 6, 12], index=0, key="wiz_interval")
        data["schedule_interval"] = interval

    if mode == "custom":
        custom = st.text_input(
            "Cron expression",
            value=data.get("schedule_custom", "0 9 * * *"),
            help="Standard 5-field cron: minute hour day-of-month month day-of-week",
        )
        data["schedule_custom"] = custom

    # Preview
    cron = _build_cron(
        mode,
        data.get("schedule_hour", 9),
        data.get("schedule_minute", 0),
        data.get("schedule_weekday", "Monday"),
        data.get("schedule_interval", 1),
        data.get("schedule_custom", "0 9 * * *"),
    )
    human = _cron_to_human(cron)
    st.code(f"Cron: {cron}\n{human}", language=None)

    return True


def _render_step_tools() -> bool:
    """Render Step 3: Tools & Inputs."""
    st.markdown("#### Step 3: Tools & Inputs")
    st.markdown("Select the tools this task will use to gather information.")

    data = st.session_state.wizard_data
    tools = data.get("tools", [])

    # Tool categories
    all_tools = []
    for cat, cat_tools in TOOL_CATEGORIES.items():
        st.markdown(f"**{cat}**")
        cat_cols = st.columns([1] * min(len(cat_tools), 4))
        for i, tool in enumerate(cat_tools):
            with cat_cols[i % len(cat_cols)]:
                desc = TOOL_FIELD_DEFS.get(tool, [{}])[0].get("help", tool) if TOOL_FIELD_DEFS.get(tool) else tool
                is_selected = tool in tools
                if st.checkbox(f"`{tool}`", value=is_selected, key=f"tool_{tool}"):
                    if tool not in tools:
                        tools.append(tool)
                st.caption(desc[:60])

    data["tools"] = tools

    if not tools:
        st.warning("Select at least one tool above.")
        return False

    st.markdown("---")
    st.markdown("##### Tool Inputs")

    # Show inputs for selected tools
    for tool in tools:
        fields = TOOL_FIELD_DEFS.get(tool, [])
        if not fields:
            continue
        with st.expander(f"⚙️ {tool} inputs", expanded=True):
            for field in fields:
                key = field["key"]
                default = data.get("inputs", {}).get(key, field.get("default", ""))
                label = field.get("label", key)
                ftype = field.get("type", "text")

                if ftype == "number":
                    try:
                        default_num = int(default) if default else int(field.get("default", 0))
                    except (TypeError, ValueError):
                        default_num = int(field.get("default", 0))
                    value = st.number_input(label, value=default_num, step=1, key=f"input_{tool}_{key}")
                    data.setdefault("inputs", {})[key] = value
                elif ftype == "text_area":
                    value = st.text_area(label, value=str(default or ""), key=f"input_{tool}_{key}", height=80)
                    if value.strip():
                        data.setdefault("inputs", {})[key] = value.strip()
                else:
                    value = st.text_input(label, value=str(default or ""), key=f"input_{tool}_{key}")
                    if value.strip():
                        data.setdefault("inputs", {})[key] = value.strip()

    # Extra inputs editor
    st.markdown("---")
    st.markdown("##### Extra Inputs")
    st.caption("Add any additional key/value pairs not covered above.")
    extra_rows = []
    for k, v in data.get("extra_inputs", {}).items():
        extra_rows.append({"key": k, "value": json.dumps(v) if not isinstance(v, str) else v})
    extra_data = st.data_editor(
        extra_rows or [{"key": "", "value": ""}],
        num_rows="dynamic",
        column_config={"key": st.column_config.TextColumn("Key"), "value": st.column_config.TextColumn("Value")},
        key="extra_inputs_editor",
    )
    extra = {}
    for row in extra_data:
        k = str(row.get("key", "")).strip()
        v = str(row.get("value", "")).strip()
        if k:
            try:
                extra[k] = json.loads(v)
            except json.JSONDecodeError:
                extra[k] = v
    data["extra_inputs"] = extra

    return len(tools) > 0


def _render_step_review() -> tuple[bool, str]:
    """Render Step 4: Review. Returns (is_valid, cron)."""
    st.markdown("#### Step 4: Review & Save")
    st.markdown("Review your task configuration before saving.")

    data = st.session_state.wizard_data

    # Validation
    errors = []
    if not data.get("name", "").strip():
        errors.append("Task name is required.")
    if not data.get("goal", "").strip():
        errors.append("Goal is required.")
    if len(data.get("goal", "")) < 10:
        errors.append("Goal should be at least 10 characters.")
    if not data.get("tools"):
        errors.append("At least one tool must be selected.")

    cron = _build_cron(
        data.get("schedule_mode", "daily"),
        data.get("schedule_hour", 9),
        data.get("schedule_minute", 0),
        data.get("schedule_weekday", "Monday"),
        data.get("schedule_interval", 1),
        data.get("schedule_custom", "0 9 * * *"),
    )
    human = _cron_to_human(cron)

    if errors:
        for e in errors:
            st.error(e)
        return False, cron

    # Summary
    st.markdown("""
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
        <div>
            <h3 style="margin:0;">{}</h3>
            <span class="badge {}">{}</span>
        </div>
    </div>
    <table style="width:100%;font-size:13px;">
        <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Goal</td><td style="color:var(--text-primary);padding:4px 0;">{}</td></tr>
        <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Schedule</td><td style="color:var(--accent);padding:4px 0;font-family:var(--font-mono);">{}</td></tr>
        <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Tools</td><td style="color:var(--text-primary);padding:4px 0;">{}</td></tr>
    </table>
</div>
""".format(
        data.get("name", ""),
        "badge-success" if data.get("enabled") else "badge-muted",
        "Enabled" if data.get("enabled") else "Disabled",
        data.get("goal", "")[:200],
        f"{cron} — {human}",
        ", ".join(f"`{t}`" for t in data.get("tools", [])),
    ), unsafe_allow_html=True)

    return True, cron


def _save_task() -> bool:
    """Save the task to disk and database."""
    data = st.session_state.wizard_data
    cron = _build_cron(
        data.get("schedule_mode", "daily"),
        data.get("schedule_hour", 9),
        data.get("schedule_minute", 0),
        data.get("schedule_weekday", "Monday"),
        data.get("schedule_interval", 1),
        data.get("schedule_custom", "0 9 * * *"),
    )
    all_inputs = dict(data.get("inputs", {}))
    all_inputs.update(data.get("extra_inputs", {}))

    task = TaskDefinition(
        name=data.get("name", "").strip(),
        schedule=cron,
        goal=data.get("goal", "").strip(),
        tools=data.get("tools", []),
        inputs=all_inputs,
        enabled=data.get("enabled", True),
    )
    tasks_dir = get_project_root() / "tasks"
    save_task(task, tasks_dir)
    get_db().upsert_task(task)
    return True


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()

    st.markdown('<h1 class="page-title">Create Task</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Build a new monitoring task step by step</p>', unsafe_allow_html=True)
    st.markdown("")

    _init_wizard_state()

    step = st.session_state.wizard_step

    _render_progress(step)

    st.markdown("")

    # Step content
    step_valid = True
    cron = ""

    if step == 0:
        step_valid = _render_step_basics()
    elif step == 1:
        step_valid = _render_step_schedule()
    elif step == 2:
        step_valid = _render_step_tools()
    elif step == 3:
        step_valid, cron = _render_step_review()

    st.markdown("")

    # Navigation buttons
    col_back, col_next, col_save = st.columns([1, 1, 1])
    with col_back:
        if step > 0:
            if st.button("← Back", use_container_width=True):
                st.session_state.wizard_step -= 1
                st.rerun()
    with col_next:
        if step < 3:
            if st.button("Next →", use_container_width=True, type="primary"):
                if step_valid:
                    st.session_state.wizard_step += 1
                    st.rerun()
                else:
                    st.error("Please fix the errors above before continuing.")
        else:
            if st.button("✅ Save Task", use_container_width=True, type="primary"):
                if _save_task():
                    st.success(f"Task '{st.session_state.wizard_data.get('name')}' created successfully!")
                    st.balloons()
                    # Reset wizard
                    for key in list(st.session_state.keys()):
                        if key.startswith("wizard") or key.startswith("tool_") or key.startswith("input_") or key.startswith("mode_") or key.startswith("wiz_") or key == "_prev_template" or key == "extra_inputs_editor":
                            del st.session_state[key]
                    st.session_state.wizard_step = 0
                    st.session_state.wizard_data = {
                        "template": "Blank", "name": "", "goal": "", "tools": [],
                        "inputs": {}, "schedule_mode": "daily", "schedule_hour": 9,
                        "schedule_minute": 0, "schedule_weekday": "Monday",
                        "schedule_interval": 1, "schedule_custom": "0 9 * * *", "enabled": True,
                        "extra_inputs": {},
                    }
                    time.sleep(1.5)
                    st.switch_page("pages/2_tasks.py")
    with col_save:
        if st.button("Cancel", use_container_width=True):
            st.session_state.wizard_step = 0
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


import time
main()
