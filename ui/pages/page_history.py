"""History page — full run history timeline."""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

import streamlit as st
import streamlit.components.v1 as components

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
        if delta.days > 0:
            return f"{delta.days}d ago"
        if delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        if delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
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
        if dur < 3600:
            return f"~{int(dur // 60)}m {int(dur % 60)}s"
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
    except Exception:
        data = None

    summary_source = ""
    if isinstance(data, dict):
        for key in ("summary", "text", "message", "result", "value"):
            candidate = data.get(key)
            if isinstance(candidate, str) and candidate.strip():
                summary_source = candidate
                break
        if not summary_source:
            for value in data.values():
                if isinstance(value, str) and value.strip():
                    summary_source = value
                    break
    if not summary_source:
        summary_source = result_json_str

    cleaned = clean_result_text(summary_source)
    cleaned = re.sub(r"<[^>]+>", "", cleaned or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:150]


def _get_dot_color(status: str) -> str:
    status = (status or "").lower()
    if status in ("success", "completed"):
        return "var(--success)"
    if status in ("error", "failed"):
        return "var(--error)"
    if status == "running":
        return "var(--warning)"
    return "var(--muted)"


def _build_timeline_html(runs: list[dict]) -> str:
    items = []
    for run in runs:
        status = run.get("status", "unknown")
        dot_color = _get_dot_color(status)
        task_name = run.get("task_name", "Unknown")
        result_preview = _get_result_summary(run.get("result_json"))
        started = run.get("started_at", "")
        finished = run.get("finished_at", "")
        error = run.get("error", "")
        duration = _duration_str(started, finished) if finished else ("Running..." if status == "running" else "—")
        started_label = _format_ts(started) if started else "—"

        status_map = {
            "success": ("badge-success", "Success"),
            "error": ("badge-error", "Error"),
            "running": ("badge-running", "Running"),
        }
        badge_class, badge_label = status_map.get(status, ("badge-muted", status.title()))

        error_html = (
            f'<div class="timeline-error">⚠️ {escape_html(error[:150])}</div>' if error else ""
        )
        preview_html = (
            f'<div class="timeline-result-preview">💬 {escape_html(result_preview)}</div>' if result_preview else ""
        )

        items.append(
            f"""
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
            <span>🕐 {started_label}</span>
            <span>⏱ {duration}</span>
        </div>
        {error_html}
        {preview_html}
    </div>
</div>
"""
        )
    return f"""
<style>
    :root {{
        --timeline-bg: #0f1117;
        --timeline-card: #1a1d27;
        --timeline-border: #2e3347;
        --timeline-subtle: rgba(255, 255, 255, 0.45);
        font-family: 'Inter', system-ui, sans-serif;
    }}
    body {{
        margin: 0;
        background: transparent;
        color: #f8fbff;
    }}
    .timeline {{
        display: flex;
        flex-direction: column;
        gap: 0;
    }}
    .timeline-item {{
        display: flex;
        gap: 16px;
        padding-bottom: 24px;
    }}
    .timeline-line {{
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 20px;
        flex-shrink: 0;
    }}
    .timeline-connector {{
        width: 2px;
        flex: 1;
        background: var(--timeline-border);
        margin-top: 8px;
        border-radius: 99px;
    }}
    .timeline-content {{
        flex: 1;
        background: var(--timeline-card);
        border: 1px solid var(--timeline-border);
        border-radius: 12px;
        padding: 20px 24px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }}
    .timeline-content-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }}
    .timeline-task-name {{
        font-size: 13px;
        font-weight: 600;
        color: #ffffff;
    }}
    .timeline-run-meta {{
        font-size: 11px;
        color: var(--timeline-subtle);
        display: flex;
        gap: 14px;
        flex-wrap: wrap;
    }}
    .timeline-result-preview {{
        font-size: 12px;
        color: #f8fbff;
        line-height: 1.5;
    }}
    .timeline-error {{
        font-size: 12px;
        color: #fed7d7;
        margin-top: 4px;
    }}
</style>
<div class="timeline">
    {''.join(items)}
</div>
"""


def _render_summary_row(runs: list[dict]) -> None:
    status_counts = Counter(r.get("status", "unknown").lower() for r in runs)
    summary_cols = st.columns(4)
    summary_cols[0].metric("Success", status_counts.get("success", 0))
    summary_cols[1].metric("Error", status_counts.get("error", 0))
    summary_cols[2].metric("Running", status_counts.get("running", 0))
    summary_cols[3].metric("Total", len(runs))


def main() -> None:
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()

    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Run History</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Complete timeline of all task executions</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

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

    _render_summary_row(runs)

    timeline_html = _build_timeline_html(runs)
    timeline_height = min(1200, max(320, 200 + len(runs) * 120))
    components.html(timeline_html, height=timeline_height, scrolling=True)
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
