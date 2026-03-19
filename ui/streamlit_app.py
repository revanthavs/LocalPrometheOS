"""LocalPrometheOS — Streamlit Multi-Page App Entry Point."""
from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="LocalPrometheOS",
    page_icon="🖥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load design system CSS
css_path = Path(__file__).parent / "styles" / "custom.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# Page definitions — controls sidebar nav and page files
PAGES = {
    "Dashboard": {
        "path": "pages/1_dashboard.py",
        "icon": "📊",
        "desc": "System overview and recent results",
    },
    "Tasks": {
        "path": "pages/2_tasks.py",
        "icon": "📋",
        "desc": "Manage all monitoring tasks",
    },
    "Results": {
        "path": "pages/5_results.py",
        "icon": "📈",
        "desc": "View task execution results",
    },
    "History": {
        "path": "pages/7_history.py",
        "icon": "🕐",
        "desc": "Full run history timeline",
    },
    "Logs": {
        "path": "pages/6_logs.py",
        "icon": "📝",
        "desc": "Application logs",
    },
}

# Build page links for sidebar
page_links = []
for name, info in PAGES.items():
    icon = info["icon"]
    page_links.append(
        st.Page(
            str(Path(__file__).parent / info["path"]),
            title=f"{icon}  {name}",
            icon=icon,
            default=False,
        )
    )

# Create / Edit are top-level sections, not full pages
page_links.extend([
    st.Page(
        str(Path(__file__).parent / "pages" / "3_create_task.py"),
        title="Create Task",
        icon="➕",
        default=False,
    ),
    st.Page(
        str(Path(__file__).parent / "pages" / "4_edit_task.py"),
        title="Edit Task",
        icon="✏️",
        default=False,
    ),
])

pg = st.navigation(page_links)
pg.run()
