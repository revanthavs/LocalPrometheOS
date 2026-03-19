"""Shared state and initialization for all UI pages."""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys
from typing import Any, List, Optional, Tuple

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.config import load_config
from database.db import Database
from tasks.task_definition import TaskDefinition, load_tasks


def get_project_root() -> Path:
    return PROJECT_ROOT


def get_config():
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    return st.session_state.config


def get_db() -> Database:
    if "db" not in st.session_state:
        config = get_config()
        st.session_state.db = Database(Path(config.storage.db_path))
        st.session_state.db.init_db()
    return st.session_state.db


def get_tasks_dir() -> Path:
    return get_project_root() / "tasks"


def get_all_tasks() -> List[TaskDefinition]:
    if "all_tasks" not in st.session_state:
        st.session_state.all_tasks = load_tasks(get_tasks_dir())
    return st.session_state.all_tasks


def refresh_tasks() -> None:
    st.session_state.all_tasks = load_tasks(get_tasks_dir())


def get_results() -> List[dict]:
    return get_db().get_last_results()


def get_logs(limit: int = 200) -> List[dict]:
    return get_db().get_recent_logs(limit)


def get_run_history(
    task_name: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    db = get_db()
    return db.get_run_history(task_name, limit)


def get_task_stats() -> dict:
    db = get_db()
    return db.get_task_stats()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text and decode HTML entities."""
    if not isinstance(text, str):
        return str(text)
    # First decode HTML entities so they become regular chars, then strip tags
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ').replace('&apos;', "'")
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _unwrap_json_string(text: str) -> str:
    """If text looks like a JSON string, parse it and return the extracted value."""
    if not isinstance(text, str):
        return str(text)
    text = text.strip()
    # Check if it looks like a JSON object or array
    if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
        try:
            parsed = json.loads(text)
            # Try common field names
            for key in ('summary', 'text', 'content', 'message', 'result', 'value'):
                if key in parsed and isinstance(parsed[key], str):
                    return parsed[key]
            # Return first string value found
            for v in parsed.values():
                if isinstance(v, str):
                    return v
            return text
        except json.JSONDecodeError:
            # Try decoding common HTML entities that may have been double-encoded
            import html
            unescaped = html.unescape(text)
            try:
                parsed = json.loads(unescaped)
                for key in ('summary', 'text', 'content', 'message', 'result', 'value'):
                    if key in parsed and isinstance(parsed[key], str):
                        return parsed[key]
                for v in parsed.values():
                    if isinstance(v, str):
                        return v
            except (json.JSONDecodeError, ValueError):
                pass
            return text
    return text


def clean_result_text(value: Any) -> str:
    """
    Clean a result field that may contain:
    1. Raw HTML tags (strip them)
    2. JSON strings (unwrap them)
    3. Plain text (return as-is)
    """
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if not isinstance(value, str):
        return str(value)

    # First try unwrapping JSON strings (might reveal plain text or more JSON)
    cleaned = _unwrap_json_string(value)
    # If we got back something still looking like JSON, try parsing again
    if cleaned != value:
        cleaned = _unwrap_json_string(cleaned)
    # Strip HTML tags and decode HTML entities
    cleaned = _strip_html(cleaned)
    # Final pass: remove any remaining HTML tag fragments that might have been missed
    cleaned = re.sub(r'<\/?[a-zA-Z][^>]*>', '', cleaned)
    return cleaned if cleaned else str(value)


def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent HTML injection and breakage."""
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
