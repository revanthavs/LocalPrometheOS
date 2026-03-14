"""Streamlit dashboard for LocalPrometheOS."""
from __future__ import annotations

from pathlib import Path
import json
import streamlit as st

from config.config import load_config
from database.db import Database
from tasks.task_definition import load_tasks


st.set_page_config(page_title="LocalPrometheOS", layout="wide")

config = load_config()
db = Database(Path(config.storage.db_path))
db.init_db()

st.title("LocalPrometheOS — Autonomous AI monitoring powered by local models.")

st.header("Dashboard")
results = db.get_last_results()
if results:
    for row in results:
        with st.expander(f"{row['name']} (last status: {row.get('status')})"):
            st.write("Goal:", row.get("goal"))
            st.write("Schedule:", row.get("schedule"))
            st.write("Last result:")
            st.write(row.get("result_text"))
else:
    st.info("No task runs recorded yet.")

st.header("Tasks")
all_tasks = load_tasks(Path(__file__).resolve().parents[1] / "tasks")
if all_tasks:
    for task in all_tasks:
        st.write(
            {
                "name": task.name,
                "schedule": task.schedule,
                "enabled": task.enabled,
                "tools": task.tools,
                "goal": task.goal,
            }
        )
else:
    st.info("No tasks found.")

st.header("Results")
if results:
    for row in results:
        st.subheader(row["name"])
        result_json = row.get("result_json")
        if result_json:
            try:
                st.json(json.loads(result_json))
            except json.JSONDecodeError:
                st.write(result_json)
        else:
            st.write("No results yet.")

st.header("Logs")
logs = db.get_recent_logs()
if logs:
    st.table(logs)
else:
    st.info("No logs yet.")
