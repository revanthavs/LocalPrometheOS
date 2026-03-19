"""Edit Task page — edit an existing task."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import get_all_tasks, get_project_root, get_db, refresh_tasks
from tasks.task_definition import TaskDefinition, save_task, load_tasks
from ui.components.system_panel import render_system_panel

TOOL_FIELD_DEFS: Dict[str, List[Dict[str, Any]]] = {
    "web_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "max_results", "label": "Max results", "type": "number", "default": 5}],
    "crypto_price": [{"key": "coin_id", "label": "Coin ID", "type": "text", "default": "bitcoin"}, {"key": "vs_currency", "label": "Quote currency", "type": "text", "default": "usd"}],
    "crypto_news": [{"key": "query", "label": "Search query", "type": "text", "default": "bitcoin"}, {"key": "limit", "label": "Max items", "type": "number", "default": 5}],
    "news_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "limit", "label": "Max items", "type": "number", "default": 5}],
    "arxiv_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "max_results", "label": "Max results", "type": "number", "default": 5}],
    "wikipedia_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "max_results", "label": "Max results", "type": "number", "default": 5}],
    "reddit_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "limit", "label": "Max posts", "type": "number", "default": 10}],
    "github_search": [{"key": "query", "label": "Search query", "type": "text", "default": ""}, {"key": "per_page", "label": "Max repos", "type": "number", "default": 10}],
    "hn_top": [{"key": "limit", "label": "Max stories", "type": "number", "default": 10}],
    "rss_reader": [{"key": "url", "label": "RSS feed URL", "type": "text", "default": ""}, {"key": "limit", "label": "Max items", "type": "number", "default": 5}],
    "http_fetch": [{"key": "url", "label": "URL", "type": "text", "default": ""}, {"key": "timeout", "label": "Timeout (seconds)", "type": "number", "default": 15}, {"key": "max_chars", "label": "Max characters", "type": "number", "default": 5000}],
    "filesystem_read": [{"key": "path", "label": "File path", "type": "text", "default": ""}, {"key": "max_chars", "label": "Max characters", "type": "number", "default": 5000}],
    "market_sentiment": [{"key": "text", "label": "Text to analyze", "type": "text_area", "default": ""}],
}

TOOL_CATEGORIES = {
    "🔍 Search": ["web_search", "news_search", "reddit_search", "github_search", "hn_top", "wikipedia_search", "arxiv_search"],
    "💰 Crypto": ["crypto_price", "crypto_news"],
    "📡 Data": ["rss_reader", "http_fetch", "filesystem_read"],
    "🧠 Analysis": ["market_sentiment"],
}

SCHEDULE_MODES = {"daily": {"label": "Daily", "icon": "📅", "desc": "Once a day"}, "weekly": {"label": "Weekly", "icon": "📆", "desc": "Once a week"}, "hourly": {"label": "Hourly", "icon": "⏰", "desc": "Every N hours"}, "custom": {"label": "Custom", "icon": "⚙️", "desc": "Cron expression"}}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_MAP = {name: i for i, name in enumerate(WEEKDAYS)}


def _infer_schedule_mode(schedule: str) -> tuple[str, dict]:
    parts = schedule.split()
    if len(parts) != 5:
        return "custom", {"custom": schedule}
    minute, hour, dom, month, dow = parts
    if dom == "*" and month == "*" and dow == "*":
        if hour.startswith("*/") and minute == "0":
            return "hourly", {"interval": int(hour.replace("*/", ""))}
        if hour.isdigit() and minute.isdigit():
            return "daily", {"hour": int(hour), "minute": int(minute)}
    if dom == "*" and month == "*" and dow.isdigit():
        day_num = int(dow)
        day_name = WEEKDAYS[day_num] if day_num < 7 else "Monday"
        return "weekly", {"hour": int(hour), "minute": int(minute), "weekday": day_name}
    return "custom", {"custom": schedule}


def _build_cron(mode: str, hour: int, minute: int, weekday: str = "Monday", interval: int = 1, custom: str = "") -> str:
    if mode == "daily":
        return f"{minute} {hour} * * *"
    elif mode == "weekly":
        dow = WEEKDAY_MAP.get(weekday, 1)
        return f"{minute} {hour} * * {dow}"
    elif mode == "hourly":
        return f"0 */{interval} * * *"
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


def _load_task_data(task_name: str) -> Dict[str, Any]:
    tasks = get_all_tasks()
    task = next((t for t in tasks if t.name == task_name), None)
    if not task:
        return {}
    sched_mode, sched_meta = _infer_schedule_mode(task.schedule)
    return {
        "name": task.name,
        "goal": task.goal,
        "tools": task.tools,
        "inputs": task.inputs,
        "schedule_mode": sched_mode,
        "schedule_hour": sched_meta.get("hour", 9),
        "schedule_minute": sched_meta.get("minute", 0),
        "schedule_weekday": sched_meta.get("weekday", "Monday"),
        "schedule_interval": sched_meta.get("interval", 1),
        "schedule_custom": sched_meta.get("custom", task.schedule),
        "enabled": task.enabled,
        "source_file": task.source_file,
    }


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()

    st.markdown('<h1 class="page-title">Edit Task</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Modify an existing monitoring task</p>', unsafe_allow_html=True)
    st.markdown("")

    all_tasks = get_all_tasks()
    if not all_tasks:
        st.info("No tasks available. Create one first.")
        if st.button("➕ Create Task"):
            st.switch_page("pages/3_create_task.py")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    task_names = [t.name for t in all_tasks]

    # Select task
    selected = st.selectbox("Select a task to edit", task_names)

    # Load task into session state
    if st.session_state.get("_edit_task_name") != selected:
        st.session_state._edit_task_name = selected
        st.session_state._edit_data = _load_task_data(selected)

    data = st.session_state._edit_data
    original_name = selected

    # Tab: Basic Info / Schedule / Tools / Review
    tab_basic, tab_sched, tab_tools, tab_review = st.tabs(["📝 Basics", "⏰ Schedule", "🔧 Tools", "👁 Review"])

    errors = []

    with tab_basic:
        st.markdown("#### Task Basics")
        name = st.text_input("Task name *", value=data.get("name", ""), key="edit_name")
        goal = st.text_area("Goal *", value=data.get("goal", ""), key="edit_goal", height=120)
        enabled = st.toggle("Task enabled", value=data.get("enabled", True), key="edit_enabled")
        data["name"] = name
        data["goal"] = goal
        data["enabled"] = enabled

    with tab_sched:
        st.markdown("#### Schedule")
        mode = data.get("schedule_mode", "daily")
        mode_options = list(SCHEDULE_MODES.keys())
        mode = st.selectbox("Schedule type", mode_options, index=mode_options.index(mode) if mode in mode_options else 0, format_func=lambda x: f"{SCHEDULE_MODES[x]['icon']} {SCHEDULE_MODES[x]['label']}", key="edit_sched_mode")
        data["schedule_mode"] = mode

        if mode in ("daily", "weekly"):
            col_h, col_m = st.columns([1, 1])
            with col_h:
                hour = st.number_input("Hour (0-23)", 0, 23, int(data.get("schedule_hour", 9)), key="edit_hour")
            with col_m:
                minute = st.number_input("Minute (0-59)", 0, 59, int(data.get("schedule_minute", 0)), key="edit_minute")
            data["schedule_hour"] = hour
            data["schedule_minute"] = minute

        if mode == "weekly":
            weekday = st.selectbox("Day of week", WEEKDAYS, index=WEEKDAYS.index(data.get("schedule_weekday", "Monday")), key="edit_weekday")
            data["schedule_weekday"] = weekday

        if mode == "hourly":
            interval = st.selectbox("Run every N hours", [1, 2, 3, 4, 6, 12], index=0, key="edit_interval")
            data["schedule_interval"] = interval

        if mode == "custom":
            custom = st.text_input("Cron expression", value=data.get("schedule_custom", "0 9 * * *"), key="edit_custom")
            data["schedule_custom"] = custom

        cron = _build_cron(mode, data.get("schedule_hour", 9), data.get("schedule_minute", 0), data.get("schedule_weekday", "Monday"), data.get("schedule_interval", 1), data.get("schedule_custom", "0 9 * * *"))
        st.code(f"{cron} — {_cron_to_human(cron)}")

    with tab_tools:
        st.markdown("#### Tools")
        tools = data.get("tools", [])
        for cat, cat_tools in TOOL_CATEGORIES.items():
            st.markdown(f"**{cat}**")
            cat_cols = st.columns([1] * min(len(cat_tools), 4))
            for i, tool in enumerate(cat_tools):
                with cat_cols[i % len(cat_cols)]:
                    is_selected = tool in tools
                    if st.checkbox(f"`{tool}`", value=is_selected, key=f"edit_tool_{tool}"):
                        if tool not in tools:
                            tools.append(tool)
                    elif tool in tools:
                        tools.remove(tool)
        data["tools"] = tools

        st.markdown("---")
        st.markdown("##### Tool Inputs")
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
                        value = st.number_input(label, value=default_num, step=1, key=f"edit_input_{tool}_{key}")
                        data.setdefault("inputs", {})[key] = value
                    elif ftype == "text_area":
                        value = st.text_area(label, value=str(default or ""), key=f"edit_input_{tool}_{key}", height=80)
                        if value.strip():
                            data.setdefault("inputs", {})[key] = value.strip()
                    else:
                        value = st.text_input(label, value=str(default or ""), key=f"edit_input_{tool}_{key}")
                        if value.strip():
                            data.setdefault("inputs", {})[key] = value.strip()

    with tab_review:
        st.markdown("#### Review")
        # Validate
        errors = []
        if not data.get("name", "").strip():
            errors.append("Task name is required.")
        if not data.get("goal", "").strip():
            errors.append("Goal is required.")
        if not data.get("tools"):
            errors.append("At least one tool must be selected.")
        if errors:
            for e in errors:
                st.error(e)

        cron = _build_cron(mode, data.get("schedule_hour", 9), data.get("schedule_minute", 0), data.get("schedule_weekday", "Monday"), data.get("schedule_interval", 1), data.get("schedule_custom", "0 9 * * *"))
        st.markdown(f"""
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
                <div>
                    <h3 style="margin:0;">{data.get('name', '')}</h3>
                    <span class="badge {'badge-success' if data.get('enabled') else 'badge-muted'}">{'Enabled' if data.get('enabled') else 'Disabled'}</span>
                </div>
            </div>
            <table style="width:100%;font-size:13px;">
                <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Goal</td><td style="color:var(--text-primary);padding:4px 0;">{data.get('goal', '')[:200]}</td></tr>
                <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Schedule</td><td style="color:var(--accent);padding:4px 0;font-family:var(--font-mono);">{cron} — {_cron_to_human(cron)}</td></tr>
                <tr><td style="color:var(--text-muted);padding:4px 8px 4px 0;">Tools</td><td style="color:var(--text-primary);padding:4px 0;">{', '.join(f'`{t}`' for t in data.get('tools', []))}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    col_s, col_c, col_del = st.columns([1, 1, 1])
    with col_s:
        save_clicked = st.button("💾 Save Changes", type="primary", use_container_width=True, disabled=bool(errors))
    with col_c:
        if st.button("Cancel", use_container_width=True):
            st.switch_page("pages/2_tasks.py")
    with col_del:
        if st.button("🗑 Delete Task", use_container_width=True):
            st.session_state._confirm_delete = True

    if st.session_state.get("_confirm_delete", False):
        st.warning("⚠️ Are you sure you want to delete this task? This cannot be undone.")
        col_y, col_n = st.columns(2)
        with col_y:
            if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                task = next((t for t in all_tasks if t.name == original_name), None)
                if task and task.source_file and task.source_file.exists():
                    task.source_file.unlink()
                refresh_tasks()
                st.success(f"Task '{original_name}' deleted.")
                st.session_state._confirm_delete = False
                time.sleep(1)
                st.switch_page("pages/2_tasks.py")
        with col_n:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state._confirm_delete = False
                st.rerun()

    if save_clicked:
        if errors:
            st.error("Please fix the errors above.")
        else:
            task = TaskDefinition(
                name=data.get("name", "").strip(),
                schedule=cron,
                goal=data.get("goal", "").strip(),
                tools=data.get("tools", []),
                inputs=data.get("inputs", {}),
                enabled=data.get("enabled", True),
            )
            tasks_dir = get_project_root() / "tasks"
            new_path = save_task(task, tasks_dir)
            # Delete old file if name changed
            old_task = next((t for t in all_tasks if t.name == original_name), None)
            if old_task and old_task.source_file and old_task.source_file.exists():
                if old_task.source_file != new_path:
                    old_task.source_file.unlink()
            get_db().upsert_task(task)
            refresh_tasks()
            st.success(f"Task '{task.name}' updated successfully!")
            st.balloons()
            time.sleep(1.5)
            st.switch_page("pages/2_tasks.py")

    st.markdown('</div>', unsafe_allow_html=True)


main()
