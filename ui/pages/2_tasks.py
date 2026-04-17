"""Tasks page — manage and run all tasks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys
import os

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import (
    clean_result_text, get_all_tasks, get_results, refresh_tasks,
    get_db, get_config, escape_html,
)

from ui.components.result_cards import render_result_card
from ui.components.system_panel import render_system_panel


def _relative_time(iso_timestamp: Optional[str]) -> str:
    if not iso_timestamp:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days > 30:
            return iso_timestamp[:10]
        if delta.days > 0:
            return f"{delta.days}d ago"
        if delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        if delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        return "Just now"
    except Exception:
        return iso_timestamp[:16]


def _extract_result_summary(result_row: Optional[dict]) -> str:
    if not result_row:
        return ""

    summary_source = ""
    json_payload = {}
    if result_row.get("result_json"):
        try:
            json_payload = json.loads(result_row["result_json"])
        except json.JSONDecodeError:
            pass

    for key in ("summary", "text", "result", "message", "value"):
        candidate = json_payload.get(key)
        if isinstance(candidate, str) and candidate.strip():
            summary_source = candidate
            break

    if not summary_source:
        summary_source = result_row.get("result_text", "")

    if not summary_source:
        return ""

    cleaned = clean_result_text(summary_source)
    cleaned = " ".join(cleaned.split())
    return cleaned[:160]


def _last_run_label(result_row: Optional[dict]) -> str:
    if not result_row:
        return ""
    for key in ("finished_at", "started_at"):
        ts = result_row.get(key)
        if ts:
            return _relative_time(ts)
    return ""
from models.lmstudio_client import LMStudioClient
from orchestrator.agent_controller import AgentController
from tools.builtin_tools import ToolContext, build_registry
from tools.mcp_client import MCPClient


def _build_controller():
    config = get_config()
    lm_client = LMStudioClient(
        base_url=config.lmstudio.base_url,
        model=config.lmstudio.model,
        temperature=config.lmstudio.temperature,
        max_tokens=config.lmstudio.max_tokens,
        timeout=config.lmstudio.timeout,
    )
    project_root = Path(__file__).resolve().parents[2]
    allowed_dirs = [
        (project_root / d).resolve()
        for d in config.filesystem.allowed_dirs
    ]
    tool_registry = build_registry(ToolContext(lm_client=lm_client, filesystem_allowed_dirs=allowed_dirs))
    if config.mcp.servers:
        mcp_client = MCPClient(config.mcp.servers)
        tool_registry.set_mcp_client(mcp_client)
    return AgentController(config=config, db=get_db(), tool_registry=tool_registry, lm_client=lm_client)


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()
        st.markdown("---")
        if st.button("➕ Create Task", use_container_width=True):
            st.switch_page("pages/3_create_task.py")

    # Page header
    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    col_t, col_a = st.columns([1, 1])
    with col_t:
        st.markdown('<h1 class="page-title">Tasks</h1>', unsafe_allow_html=True)
        st.markdown('<p class="page-subtitle">Manage and run your monitoring tasks</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    all_tasks = get_all_tasks()
    total_tasks = len(all_tasks)
    enabled_tasks = sum(1 for t in all_tasks if t.enabled)
    disabled_tasks = total_tasks - enabled_tasks

    results = get_results()
    results_map = {r["name"]: r for r in results}

    recent_ts = None
    for row in results:
        for key in ("finished_at", "started_at"):
            ts = row.get(key)
            if ts and (recent_ts is None or ts > recent_ts):
                recent_ts = ts
    last_run_label = _relative_time(recent_ts) if recent_ts else "No runs yet"

    stats_cols = st.columns(4)
    stats_cols[0].metric("Total tasks", total_tasks)
    stats_cols[1].metric("Enabled", enabled_tasks)
    stats_cols[2].metric("Disabled", disabled_tasks)
    stats_cols[3].metric("Last run", last_run_label)

    filter_key = st.session_state.get("task_filter", "all")
    filter_options = ["all", "enabled", "disabled"]
    filter_labels = {"all": "All Tasks", "enabled": "Enabled Only", "disabled": "Disabled Only"}
    filter_index = filter_options.index(filter_key) if filter_key in filter_options else 0

    search_value = st.session_state.get("task_search", "")

    st.markdown('<div class="task-controls-grid">', unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([1, 3, 1], gap="large")
    with col_f1:
        st.markdown('<div class="task-control-col">', unsafe_allow_html=True)
        filter_sel = st.selectbox(
            "Filter",
            options=filter_options,
            format_func=lambda x: filter_labels[x],
            index=filter_index,
            key="task_filter_selector",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with col_f2:
        st.markdown('<div class="task-control-col">', unsafe_allow_html=True)
        search_query = st.text_input(
            "Search tasks",
            value=search_value,
            placeholder="Search tasks by name or goal...",
            label_visibility="collapsed",
            key="task_search_input",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with col_f3:
        st.markdown('<div class="task-control-col task-control-actions">', unsafe_allow_html=True)
        if st.button("🔄 Refresh tasks", key="refresh_tasks_button", use_container_width=True):
            refresh_tasks()
            st.rerun()
        if st.button("🆕 Create Task", key="tasks_new_button", use_container_width=True, type="primary"):
            st.switch_page("pages/3_create_task.py")
        st.markdown('</div>', unsafe_allow_html=True)

    st.session_state["task_filter"] = filter_sel
    st.session_state["task_search"] = search_query

    filtered_tasks = all_tasks
    if filter_sel == "enabled":
        filtered_tasks = [t for t in filtered_tasks if t.enabled]
    elif filter_sel == "disabled":
        filtered_tasks = [t for t in filtered_tasks if not t.enabled]
    if search_query:
        q = search_query.lower()
        filtered_tasks = [t for t in filtered_tasks if q in t.name.lower() or q in t.goal.lower()]

    st.markdown(f"Showing **{len(filtered_tasks)}** of **{total_tasks}** tasks")

    st.markdown('</div>', unsafe_allow_html=True)
    if filtered_tasks:
        cards_per_row = 2 if len(filtered_tasks) > 1 else 1
        for row_idx in range(0, len(filtered_tasks), cards_per_row):
            row_tasks = filtered_tasks[row_idx : row_idx + cards_per_row]
            cols = st.columns(cards_per_row)
            for col, task in zip(cols, row_tasks):
                with col:
                    result_row = results_map.get(task.name)
                    _render_task_card_inline(task, result_row)
            st.markdown("")
    else:
        if search_query:
            st.info(f"No tasks match '{search_query}'. Try a different search term.")
        elif filter_sel != "all":
            st.info(f"No {filter_sel} tasks found.")

    st.markdown('</div>', unsafe_allow_html=True)


def _render_task_card_inline(task, result_row=None):
    """Render a single task card inline."""
    status = "disabled" if not task.enabled else (result_row.get("status") if result_row else "idle")
    status_map = {
        "disabled": ("badge-muted", "Disabled"),
        "success": ("badge-success", "Success"),
        "error": ("badge-error", "Error"),
        "running": ("badge-running", "Running"),
        "idle": ("badge-muted", "Idle"),
    }
    badge_class, badge_label = status_map.get(status, status_map["idle"])

    goal_preview = escape_html(task.goal[:100]) + ("..." if len(task.goal) > 100 else "")

    safe_key = task.name.replace(" ", "_").replace("/", "_")

    tools_html = "".join(f'<span class="tool-chip">{escape_html(t)}</span>' for t in task.tools[:4])
    if len(task.tools) > 4:
        tools_html += f'<span class="tool-chip tool-chip-more">+{len(task.tools)-4}</span>'
    summary_preview = _extract_result_summary(result_row)
    last_run = _last_run_label(result_row)

    card_html = f"""
    <div class="task-card" id="task-{safe_key}">
        <div class="task-card-header">
            <span class="task-card-title" title="{escape_html(task.name)}">{escape_html(task.name)}</span>
            <span class="badge {badge_class}">{badge_label}</span>
        </div>
        <div class="task-card-body">
            <p class="task-card-goal">{goal_preview}</p>
            {f'<p class="task-card-summary">{escape_html(summary_preview)}</p>' if summary_preview else ''}
            <div class="task-card-tools">
                {tools_html}
            </div>
        </div>
        <div class="task-card-footer">
            <div class="task-card-meta-row">
                <span class="task-card-meta">Tools: {len(task.tools)}</span>
                {f'<span class="task-card-meta-time">Last run {escape_html(last_run)}</span>' if last_run else ''}
            </div>
        </div>
    </div>"""

    st.html(card_html)

    col_r, col_e = st.columns(2)
    with col_r:
        run_disabled = status == "running" or not task.enabled
        if st.button("▶ Run", key=f"run_{safe_key}", use_container_width=True, disabled=run_disabled):
            _run_task(task)
    with col_e:
        if st.button("✏️ Edit", key=f"edit_{safe_key}", use_container_width=True):
            st.session_state["edit_task_name"] = task.name
            st.switch_page("pages/4_edit_task.py")


def _run_task(task):
    """Execute a task and show result inline."""
    config = get_config()
    db = get_db()
    db.upsert_task(task)

    progress_bar = st.progress(0, text=f"Running {task.name}...")
    status_text = st.empty()

    try:
        status_text.markdown("⏳ Initializing agents...")
        progress_bar.progress(20)
        controller = _build_controller()

        status_text.markdown("🔧 Planning steps...")
        progress_bar.progress(40)
        status_text.markdown("⚙️ Executing tools...")
        progress_bar.progress(70)

        result = controller.run_task(task)

        progress_bar.progress(100)
        status_text.markdown("✅ Complete!")

        st.session_state[f"last_result_{task.name}"] = result

        st.success(f"**{task.name}** completed successfully!")

        # Build a result row for the card renderer
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        import json as _json
        result_row = {
            "name": task.name,
            "status": "success",
            "finished_at": now_iso,
            "result_json": _json.dumps(result),
            "result_text": result.get("summary", ""),
            "goal": task.goal,
            "schedule": task.schedule,
        }
        with st.expander("View Result"):
            render_result_card(result_row)

    except Exception as exc:
        progress_bar.empty()
        st.error(f"Task failed: {exc}")
        st.session_state[f"last_error_{task.name}"] = str(exc)


main()
