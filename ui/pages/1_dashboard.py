"""Dashboard page — system overview, metrics, and recent results."""
from __future__ import annotations

import time

import streamlit as st

from ui.shared import get_all_tasks, get_results, get_db, get_config
from ui.components.system_panel import render_system_panel
from ui.components.result_cards import render_result_card, render_results_grid


def _relative_time(iso_timestamp):
    if not iso_timestamp:
        return "Never"
    try:
        from datetime import datetime, timezone
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


def _check_lmstudio(base_url, timeout=3):
    try:
        import urllib.request, urllib.error
        url = base_url.rstrip('/v1').rstrip('/') + "/models"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.time() - start) * 1000)
            resp.read()
            return {"connected": True, "latency_ms": latency_ms}
    except Exception:
        return {"connected": False, "latency_ms": None}


def _render_metric_card(value: str, label: str, sub: str = "", color: str = "var(--text-primary)"):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:{color};">{value}</div>
        <div class="metric-label">{label}</div>
        {f'<div class="metric-sub">{sub}</div>' if sub else ''}
    </div>
    """, unsafe_allow_html=True)


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    # Sidebar system panel
    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()
        st.markdown("---")
        st.markdown("#### Quick Actions")
        if st.button("➕ Create Task", use_container_width=True):
            st.switch_page("pages/3_create_task.py")
        if st.button("▶ Run All Enabled", use_container_width=True):
            st.info("Use CLI: `python main.py start` to run the scheduler")

    # Page header
    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">System overview and recent task results</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── System Status Bar ───────────────────────────────
    config = get_config()
    tasks = get_all_tasks()
    db = get_db()

    lm = _check_lmstudio(config.lmstudio.base_url)
    lm_status = "🟢 Connected" if lm["connected"] else "🔴 Disconnected"
    lm_latency = f" ~{lm['latency_ms']}ms" if lm["connected"] and lm["latency_ms"] else ""
    enabled_count = sum(1 for t in tasks if t.enabled)
    total_count = len(tasks)

    stats = db.get_task_stats()
    total_runs = stats.get("total_runs", 0)
    success_runs = stats.get("success_runs", 0)
    failed_runs = stats.get("failed_runs", 0)
    last_run_task = stats.get("last_run_task", "—")
    last_run_time = _relative_time(stats.get("last_run_time"))

    st.markdown(f"""
    <div style="display:flex;gap:16px;padding:12px 16px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius-md);margin-bottom:var(--space-5);flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:13px;color:var(--text-secondary);">LM Studio:</span>
            <span style="font-size:13px;font-weight:600;">{lm_status}{lm_latency}</span>
        </div>
        <div style="width:1px;background:var(--border);"></div>
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:13px;color:var(--text-secondary);">Tasks:</span>
            <span style="font-size:13px;font-weight:600;">{enabled_count} enabled / {total_count} total</span>
        </div>
        <div style="width:1px;background:var(--border);"></div>
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:13px;color:var(--text-secondary);">Last run:</span>
            <span style="font-size:13px;font-weight:600;">{last_run_task or '—'}</span>
            <span style="font-size:12px;color:var(--text-muted);">({last_run_time})</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metric Cards ───────────────────────────────────
    success_rate = int(success_runs / total_runs * 100) if total_runs > 0 else 0
    avg_dur = stats.get("avg_duration") or 0
    avg_dur_str = f"~{int(avg_dur)}s" if avg_dur else "—"

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        _render_metric_card(str(total_runs), "Total Runs", f"{success_runs} success · {failed_runs} failed")
    with m2:
        rate_color = "var(--success)" if success_rate >= 80 else "var(--warning)" if success_rate >= 50 else "var(--error)"
        _render_metric_card(f"{success_rate}%", "Success Rate", f"Last 30 days", color=rate_color)
    with m3:
        _render_metric_card(str(enabled_count), "Active Tasks", f"{total_count - enabled_count} disabled")
    with m4:
        _render_metric_card(avg_dur_str, "Avg Duration", "per successful run")

    st.markdown("")  # spacer

    # ── Recent Results ─────────────────────────────────
    results = get_results()

    col_view_all, col_actions = st.columns([1, 1])
    with col_view_all:
        st.markdown("### Recent Results")
    with col_actions:
        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("📋 All Tasks", use_container_width=True):
                st.switch_page("pages/2_tasks.py")
        with col_b:
            if st.button("📈 All Results", use_container_width=True):
                st.switch_page("pages/5_results.py")

    st.markdown("")

    if results:
        # Group into pairs
        for i in range(0, len(results), 2):
            c1, c2 = st.columns(2)
            with c1:
                render_result_card(results[i])
            if i + 1 < len(results):
                with c2:
                    render_result_card(results[i + 1])
            st.markdown("")
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-title">No results yet</div>
            <div class="empty-state-desc">Run a task or create new ones to see results here.</div>
        </div>
        """, unsafe_allow_html=True)
        col_c1, col_c2, col_c3 = st.columns([1, 1, 1])
        with col_c1:
            if st.button("➕ Create Task", use_container_width=True):
                st.switch_page("pages/3_create_task.py")

    st.markdown('</div>', unsafe_allow_html=True)


main()
