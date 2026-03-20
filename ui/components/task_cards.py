"""Task card component for displaying task summaries."""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st

# Import escape_html for safe template rendering
from ui.shared import escape_html


def _relative_time(iso_timestamp: Optional[str]) -> str:
    """Convert ISO timestamp to relative time string."""
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
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "Just now"
    except Exception:
        return str(iso_timestamp)[:16]


def _cron_to_human(schedule: str) -> str:
    """Convert cron expression to human-readable string."""
    parts = schedule.split()
    if len(parts) != 5:
        return schedule
    minute, hour, dom, month, dow = parts
    if dom == "*" and month == "*" and dow == "*":
        if hour.startswith("*/"):
            interval = hour.replace("*/", "")
            return f"Every {interval}h"
        if hour.isdigit() and minute.isdigit():
            h, m = int(hour), int(minute)
            period = "AM" if h < 12 else "PM"
            h12 = h % 12 or 12
            return f"Daily at {h12}:{m:02d} {period}"
    if dom == "*" and month == "*" and dow.isdigit():
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_name = day_names[int(dow)] if int(dow) < 7 else dow
        h, m = int(hour), int(minute)
        period = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"Every {day_name} at {h12}:{m:02d} {period}"
    return schedule


def _get_status_info(task: Any, result_row: Optional[Dict]) -> Tuple[str, str, str]:
    """Determine card status based on task and result data."""
    if not task.enabled:
        return "disabled", "Disabled", "muted"
    if result_row and result_row.get("status") == "running":
        return "running", "Running", "warning"
    if result_row and result_row.get("status") == "error":
        return "error", "Error", "error"
    if result_row and result_row.get("status") == "success":
        return "success", "Success", "success"
    return "idle", "Idle", "muted"


def render_task_card(
    task: Any,
    result_row: Optional[Dict[str, Any]] = None,
    on_run_key: Optional[str] = None,
    show_edit: bool = True,
    compact: bool = False,
) -> Optional[str]:
    """
    Render a single task card.
    Returns the name of the clicked action ('run', 'edit', 'delete') or None.
    """
    status_key, status_label, status_color = _get_status_info(task, result_row)
    status_class = f"badge-{status_color}" if status_key not in ("running", "idle") else (
        "badge-running" if status_key == "running" else "badge-muted"
    )

    goal_preview = task.goal[:120] + ("..." if len(task.goal) > 120 else "")
    schedule_human = _cron_to_human(task.schedule)
    last_run = result_row.get("finished_at") if result_row else None
    last_run_str = _relative_time(last_run)
    task_tools = task.tools[:5] if task.tools else []
    extra_tools = len(task.tools) - 5 if task.tools and len(task.tools) > 5 else 0

    # Build action key prefix
    safe_name = task.name.replace(" ", "_").replace("/", "_")
    run_key = f"run_{safe_name}"
    edit_key = f"edit_{safe_name}"
    delete_key = f"delete_{safe_name}"

    tools_html = "".join(f'<span class="tool-chip">{escape_html(t)}</span>' for t in task_tools)
    extra_html = f'<span class="tool-chip tool-chip-more">+{extra_tools} more</span>' if extra_tools > 0 else ""

    card_html = f"""
    <div class="task-card" data-task="{escape_html(task.name)}">
        <div class="task-card-header">
            <span class="task-card-title" title="{escape_html(task.name)}">{escape_html(task.name)}</span>
            <span class="badge {status_class}">{status_label}</span>
        </div>
        <p class="task-card-goal" title="{escape_html(task.goal)}">{escape_html(goal_preview)}</p>
        <div class="task-card-tools">
            <span class="tool-chip" style="font-size:10px;color:var(--text-muted);">{escape_html(schedule_human)}</span>
            {tools_html}
            {extra_html}
        </div>
        <div class="task-card-footer">
            <span class="task-card-meta">
                <span style="color:var(--text-muted);font-size:11px;">Last run:</span>
                <span style="font-size:12px;">{escape_html(last_run_str)}</span>
            </span>
        </div>
    </div>"""

    st.html(card_html)

    # Buttons are rendered outside the HTML card so they actually work
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        run_disabled = status_key == "running" or not task.enabled
        clicked_run = st.button(
            "▶ Run",
            key=run_key,
            help="Run this task now",
            use_container_width=True,
            disabled=run_disabled,
        )
        if clicked_run:
            return "run"
    with col2:
        if show_edit:
            clicked_edit = st.button(
                "✏️ Edit",
                key=edit_key,
                help="Edit this task",
                use_container_width=True,
            )
            if clicked_edit:
                return "edit"
    with col3:
        if task.enabled:
            confirm_key = f"confirm_delete_{safe_name}"
            if st.session_state.get(confirm_key, False):
                clicked_confirm = st.button(
                    "⚠ Confirm",
                    key=delete_key,
                    help="Click again to confirm deletion",
                    use_container_width=True,
                )
                st.session_state[confirm_key] = False
                if clicked_confirm:
                    return "delete"
        else:
            clicked_delete = st.button(
                "🗑 Delete",
                key=delete_key,
                help="Delete this task",
                use_container_width=True,
            )
            if clicked_delete:
                return "delete"

    # Toggle for delete confirmation
    if task.enabled:
        if st.button("🗑 Delete", key=f"del_{safe_name}", help="Delete this task"):
            st.session_state[f"confirm_delete_{safe_name}"] = True
            st.rerun()

    return None


def render_task_cards_grid(
    tasks: List[Any],
    results_map: Optional[Dict[str, Dict]] = None,
    show_edit_button: bool = True,
    compact: bool = False,
) -> Optional[str]:
    """Render all tasks as a responsive grid of cards. Returns action if triggered."""
    results_map = results_map or {}

    if not tasks:
        st.info("No tasks found. Create one to get started!")
        return None

    action = None
    num_cols = 3 if not compact else 2
    cols = st.columns(num_cols)
    for idx, task in enumerate(tasks):
        col = cols[idx % num_cols]
        with col:
            result_row = results_map.get(task.name)
            result = render_task_card(
                task,
                result_row=result_row,
                show_edit=show_edit_button,
                compact=compact,
            )
            if result:
                action = result

    return action
