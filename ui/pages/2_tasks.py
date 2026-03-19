"""Tasks page — manage and run all tasks."""
from __future__ import annotations

from pathlib import Path
import sys
import os

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import (
    get_all_tasks, get_results, refresh_tasks, get_db, get_config,
    get_project_root, escape_html,
)
from ui.components.task_cards import render_task_cards_grid
from ui.components.result_cards import render_result_card
from ui.components.system_panel import render_system_panel
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
    tool_registry = build_registry(ToolContext(lm_client=lm_client))
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
    with col_a:
        st.markdown("<div style='text-align:right;padding-top:8px;'>", unsafe_allow_html=True)
        if st.button("➕ Create New Task", type="primary"):
            st.switch_page("pages/3_create_task.py")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Refresh button
    col_r, col_f = st.columns([1, 1])
    with col_r:
        st.markdown(f"**{len(get_all_tasks())} tasks**")
    with col_f:
        if st.button("🔄 Refresh"):
            refresh_tasks()
            st.rerun()

    st.markdown("")

    # Build results map
    results = get_results()
    results_map = {r["name"]: r for r in results}

    # Filter state
    filter_key = st.session_state.get("task_filter", "all")
    filter_options = ["all", "enabled", "disabled"]
    filter_labels = {"all": "All Tasks", "enabled": "Enabled Only", "disabled": "Disabled Only"}

    col_f1, col_f2 = st.columns([1, 4])
    with col_f1:
        filter_sel = st.selectbox("Filter", options=filter_options, format_func=lambda x: filter_labels[x], index=0)
    with col_f2:
        search_query = st.text_input("Search", placeholder="Search tasks by name or goal...", label_visibility="collapsed")

    all_tasks = get_all_tasks()

    # Apply filters
    filtered_tasks = all_tasks
    if filter_sel == "enabled":
        filtered_tasks = [t for t in filtered_tasks if t.enabled]
    elif filter_sel == "disabled":
        filtered_tasks = [t for t in filtered_tasks if not t.enabled]
    if search_query:
        q = search_query.lower()
        filtered_tasks = [t for t in filtered_tasks if q in t.name.lower() or q in t.goal.lower()]

    st.markdown(f"Showing **{len(filtered_tasks)}** of **{len(all_tasks)}** tasks")

    if filtered_tasks:
        # Render as a grid
        cols = st.columns(3)
        for idx, task in enumerate(filtered_tasks):
            col = cols[idx % 3]
            with col:
                result_row = results_map.get(task.name)
                _render_task_card_inline(task, result_row)
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

    card_html = f"""
    <div class="task-card" id="task-{safe_key}">
        <div class="task-card-header">
            <span class="task-card-title" title="{escape_html(task.name)}">{escape_html(task.name)}</span>
            <span class="badge {badge_class}">{badge_label}</span>
        </div>
        <div class="task-card-body">
            <p class="task-card-goal">{goal_preview}</p>
            <div class="task-card-tools">
                {tools_html}
            </div>
        </div>
        <div class="task-card-footer">
            <span class="task-card-meta">Tools: {len(task.tools)}</span>
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
