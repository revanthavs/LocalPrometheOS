"""History page — full run history timeline."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import get_run_history, get_all_tasks, clean_result_text, escape_html
from ui.components.system_panel import render_system_panel


def _relative_time(iso_timestamp: Optional[str]) -> str:
    if not iso_timestamp:
        return "—"
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


def _duration_str(started: str, finished: str) -> str:
    try:
        s = datetime.fromisoformat(started)
        e = datetime.fromisoformat(finished)
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        dur = (e - s).total_seconds()
        if dur < 60:
            return f"~{int(dur)}s"
        elif dur < 3600:
            return f"~{int(dur // 60)}m {int(dur % 60)}s"
        else:
            return f"~{int(dur // 3600)}h {int((dur % 3600) // 60)}m"
    except Exception:
        return "—"


def _format_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return ts[:16]


def _get_result_summary(result_json_str: Optional[str]) -> str:
    if not result_json_str:
        return ""
    try:
        data = json.loads(result_json_str)
        raw_summary = data.get("summary", "") if isinstance(data, dict) else ""
    except Exception:
        raw_summary = result_json_str
    cleaned = clean_result_text(raw_summary) if raw_summary else ""
    # Additional defense: strip any remaining HTML tags that might have been missed
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    # Limit length to prevent overly long previews
    return cleaned[:100] if cleaned else ""


def _get_dot_color(status: str) -> str:
    status = (status or "").lower()
    if status in ("success", "completed"):
        return "var(--success)"
    elif status in ("error", "failed"):
        return "var(--error)"
    elif status == "running":
        return "var(--warning)"
    return "var(--muted)"


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()

    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Run History</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Complete timeline of all task executions</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Filters
    all_tasks = get_all_tasks()
    task_options = ["All Tasks"] + [t.name for t in all_tasks]
    status_options = ["All", "Success", "Error", "Running"]

    col_t, col_s, col_l = st.columns([2, 1, 1])
    with col_t:
        selected_task = st.selectbox("Task", task_options, index=0)
    with col_s:
        selected_status = st.selectbox("Status", status_options, index=0)
    with col_l:
        limit = st.selectbox("Limit", [25, 50, 100, 200], index=1)

    task_filter = selected_task if selected_task != "All Tasks" else None
    status_filter = selected_status if selected_status != "All" else None

    runs = get_run_history(task_name=task_filter, limit=limit)

    if status_filter:
        runs = [r for r in runs if r.get("status", "").lower() == status_filter.lower()]

    st.markdown(f"**{len(runs)}** execution(s)")

    if not runs:
        st.info("No runs found matching the selected filters.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Timeline
    for run in runs:
        status = run.get("status", "unknown")
        dot_color = _get_dot_color(status)
        task_name = run.get("task_name", "Unknown")
        result_preview = _get_result_summary(run.get("result_json"))
        started = run.get("started_at", "")
        finished = run.get("finished_at", "")
        error = run.get("error", "")
        duration = _duration_str(started, finished) if finished else ("Running..." if status == "running" else "—")

        status_map = {
            "success": ("badge-success", "Success"),
            "error": ("badge-error", "Error"),
            "running": ("badge-running", "Running"),
        }
        badge_class, badge_label = status_map.get(status, ("badge-muted", status.title()))

        st.markdown(f"""
<div class="timeline">
    <div class="timeline-item">
        <div class="timeline-line">
            <div class="timeline-dot" style="background:{dot_color};border-color:var(--bg-primary);"></div>
            <div class="timeline-connector"></div>
        </div>
        <div class="timeline-content">
            <div class="timeline-content-header">
                <span class="timeline-task-name">{escape_html(task_name)}</span>
                <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                    <span class="badge {badge_class}">{badge_label}</span>
                </div>
            </div>
            <div class="timeline-run-meta">
                <span>🕐 {started[:16] if started else '—'}</span>
                <span>⏱ {duration}</span>
            </div>
            {f'<div style="font-size:12px;color:var(--text-muted);margin-top:4px;">⚠️ {escape_html(error[:100])}</div>' if error else ''}
            {f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview)}</div>' if result_preview else ''}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


main()
