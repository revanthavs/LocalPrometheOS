"""Logs page — application logs with filtering."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import get_logs
from ui.components.system_panel import render_system_panel


def _format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return ts


def _get_level_style(level: str) -> tuple[str, str]:
    level = level.upper()
    if level == "ERROR":
        return "var(--error)", "badge-error"
    elif level == "WARNING":
        return "var(--warning)", "badge-warning"
    elif level == "INFO":
        return "var(--info)", "badge-info"
    elif level == "DEBUG":
        return "var(--muted)", "badge-muted"
    return "var(--text-secondary)", "badge-muted"


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()

    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Logs</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Application logs from task executions</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Filters
    col_level, col_limit = st.columns([1, 1])
    with col_level:
        level_filter = st.selectbox(
            "Log level",
            ["All", "ERROR", "WARNING", "INFO", "DEBUG"],
            index=0,
        )
    with col_limit:
        limit = st.selectbox("Show last", [50, 100, 200, 500], index=1)

    logs = get_logs(limit=limit)

    if level_filter != "All":
        logs = [l for l in logs if l.get("level", "").upper() == level_filter.upper()]

    if not logs:
        st.info("No logs found.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.markdown(f"**{len(logs)}** log entries")

    # Build display rows
    for log in logs:
        level = log.get("level", "INFO")
        level_color, level_class = _get_level_style(level)
        ts = _format_timestamp(log.get("timestamp", ""))
        message = log.get("message", "")
        run_id = log.get("run_id")

        st.markdown(f"""
        <div style="display:flex;gap:12px;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:6px;align-items:flex-start;">
            <span class="badge {level_class}" style="flex-shrink:0;margin-top:2px;">{level}</span>
            <div style="flex:1;min-width:0;">
                <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">{ts}{f' · Run #{run_id}' if run_id else ''}</div>
                <div style="font-size:13px;color:var(--text-primary);font-family:var(--font-mono);word-break:break-word;">{message}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


main()
