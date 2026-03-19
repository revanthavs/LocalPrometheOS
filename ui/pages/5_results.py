"""Results page — formatted task execution results."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.shared import get_results, get_all_tasks
from ui.components.system_panel import render_system_panel
from ui.components.result_cards import render_result_detail, render_result_card


def main():
    st.markdown('<div class="page-container">', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🖥 LocalPrometheOS")
        st.markdown("---")
        render_system_panel()
        st.markdown("---")
        if st.button("📋 All Tasks", use_container_width=True):
            st.switch_page("pages/2_tasks.py")

    st.markdown('<div class="page-header">', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">Results</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">View the latest execution results for all tasks</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    results = get_results()
    all_tasks = get_all_tasks()

    if not results:
        st.markdown("""
<div class="empty-state">
    <div class="empty-state-icon">📭</div>
    <div class="empty-state-title">No results yet</div>
    <div class="empty-state-desc">Run a task to see its results here. Results are generated automatically after each task execution.</div>
</div>
""", unsafe_allow_html=True)
        if st.button("➕ Create Task"):
            st.switch_page("pages/3_create_task.py")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Filter by task
    task_names = ["All Tasks"] + [t.name for t in all_tasks]
    selected_task = st.selectbox("Filter by task", task_names)

    filtered = results
    if selected_task != "All Tasks":
        filtered = [r for r in results if r["name"] == selected_task]

    st.markdown(f"Showing **{len(filtered)}** result(s)")

    # Toggle: card view vs detail view
    view_mode = st.radio("View", ["Card", "Detailed"], horizontal=True, label_visibility="collapsed")

    if view_mode == "Card":
        cols = st.columns(2) if len(filtered) > 1 else [1]
        for idx, row in enumerate(filtered):
            with cols[idx % len(cols)]:
                render_result_card(row, show_task_name=False)
                st.markdown("")
    else:
        for row in filtered:
            render_result_detail(row)
            st.markdown("---")

    st.markdown('</div>', unsafe_allow_html=True)


main()
