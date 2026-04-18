"""System status panel component — LM Studio, MCP, scheduler, and task status."""
from __future__ import annotations

import time
from typing import Any, Dict, List
import urllib.request
import urllib.error

import streamlit as st

from ui.shared import get_config, get_all_tasks, get_db


@st.cache_data(ttl=60)
def check_mcp_servers(server_configs_repr: str) -> List[Dict[str, Any]]:
    """Probe each configured MCP server and return status + tool count.

    server_configs_repr is a stable string key derived from the server list
    so st.cache_data can hash it.
    """
    import json as _json
    from config.config import MCPServerConfig
    from tools.mcp_client import MCPClient, MCPError

    try:
        servers_raw = _json.loads(server_configs_repr)
        servers = [MCPServerConfig(**s) for s in servers_raw]
    except Exception:
        return []

    results: List[Dict[str, Any]] = []
    for server in servers:
        try:
            client = MCPClient([server])
            tools = client.list_tools()
            results.append({
                "name": server.name,
                "transport": server.transport,
                "connected": True,
                "tool_count": len(tools),
                "error": None,
            })
        except Exception as exc:
            results.append({
                "name": server.name,
                "transport": server.transport,
                "connected": False,
                "tool_count": 0,
                "error": str(exc)[:80],
            })
    return results


@st.cache_data(ttl=60)
def check_lmstudio(base_url: str, timeout: int = 3) -> Dict[str, Any]:
    """Ping LM Studio and return connection status."""
    try:
        url = f"{base_url.rstrip('/v1').rstrip('/')}/models"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.time() - start) * 1000)
            data = resp.read()
            return {
                "connected": True,
                "latency_ms": latency_ms,
                "status": "ok",
            }
    except urllib.error.URLError:
        return {"connected": False, "latency_ms": None, "status": "connection_failed"}
    except Exception:
        return {"connected": False, "latency_ms": None, "status": "unknown_error"}


def render_system_panel() -> None:
    """Render the sidebar system status panel."""
    config = get_config()
    db = get_db()
    tasks = get_all_tasks()

    # LM Studio status
    lm = check_lmstudio(config.lmstudio.base_url, timeout=3)

    # Task counts
    total_tasks = len(tasks)
    enabled_tasks = sum(1 for t in tasks if t.enabled)

    # DB stats
    try:
        stats = db.get_task_stats()
    except Exception:
        stats = {
            "total_runs": 0, "success_runs": 0, "failed_runs": 0,
            "active_tasks": enabled_tasks, "total_tasks": total_tasks,
            "last_run_task": None, "last_run_time": None, "avg_duration": 0,
        }

    # Scheduler (check if APScheduler has jobs)
    scheduler_status = "unknown"
    scheduler_jobs = 0
    try:
        from scheduler.task_scheduler import TaskScheduler
        sched = TaskScheduler(config, db)
        if sched.scheduler.running:
            scheduler_jobs = len(sched.scheduler.get_jobs())
            scheduler_status = "active" if scheduler_jobs > 0 else "idle"
        else:
            scheduler_status = "stopped"
    except Exception:
        scheduler_status = "not_configured"

    lm_url = config.lmstudio.base_url

    st.markdown("""
<style>
.sp-header { font-size: 13px; font-weight: 700; color: #8b90a5;
              text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }
.sp-section { margin-bottom: 20px; }
.sp-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.sp-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sp-label { font-size: 12px; color: #8b90a5; flex: 1; }
.sp-value { font-size: 12px; font-weight: 600; color: #e4e7f0; }
.sp-value.success { color: #22c55e; }
.sp-value.error { color: #ef4444; }
.sp-value.warning { color: #f59e0b; }
.sp-value.accent { color: #00d4aa; }
.sp-divider { border-top: 1px solid #2e3347; margin: 14px 0; }
.sp-stat { display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 6px; }
.sp-stat-label { font-size: 12px; color: #555a70; }
.sp-stat-value { font-size: 12px; font-weight: 600; color: #e4e7f0; }
</style>
""", unsafe_allow_html=True)

    # LM Studio Section
    st.markdown('<div class="sp-header">LM Studio</div>', unsafe_allow_html=True)
    dot_color = "success" if lm["connected"] else "error"
    dot_class = f"sp-value {dot_color}"
    conn_text = f"Connected  ·  ~{lm['latency_ms']}ms" if lm["connected"] else "Disconnected"
    model_name = config.lmstudio.model

    st.markdown(f"""
<div class="sp-section">
    <div class="sp-row">
        <div class="sp-dot sp-{dot_color}" style="background: var(--{'success' if lm['connected'] else 'error'});"></div>
        <span class="sp-label">Status</span>
        <span class="{dot_class}">{conn_text}</span>
    </div>
    <div class="sp-row">
        <div class="sp-dot" style="background: #555a70;"></div>
        <span class="sp-label">Model</span>
        <span class="sp-value accent">{model_name}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="sp-divider"></div>', unsafe_allow_html=True)

    # MCP Servers Section
    if config.mcp.servers:
        import json as _json
        servers_repr = _json.dumps(
            [
                {
                    "name": s.name,
                    "transport": s.transport,
                    "command": s.command,
                    "url": s.url,
                    "env": s.env,
                    "timeout": s.timeout,
                }
                for s in config.mcp.servers
            ]
        )
        mcp_statuses = check_mcp_servers(servers_repr)

        st.markdown('<div class="sp-header">MCP Servers</div>', unsafe_allow_html=True)
        rows_html = ""
        for srv in mcp_statuses:
            dot_bg = "var(--success)" if srv["connected"] else "var(--error)"
            status_text = f"{srv['tool_count']} tools" if srv["connected"] else "Unreachable"
            status_color = "success" if srv["connected"] else "error"
            transport_badge = srv["transport"].upper()
            rows_html += f"""
<div class="sp-row">
    <div class="sp-dot" style="background:{dot_bg};"></div>
    <span class="sp-label">{srv['name']} <span style="color:#555a70;font-size:10px;">[{transport_badge}]</span></span>
    <span class="sp-value {status_color}">{status_text}</span>
</div>"""

        st.markdown(f'<div class="sp-section">{rows_html}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sp-divider"></div>', unsafe_allow_html=True)

    # Scheduler Section
    st.markdown('<div class="sp-header">Scheduler</div>', unsafe_allow_html=True)
    sched_color = {"active": "success", "idle": "warning", "stopped": "muted", "not_configured": "muted", "unknown": "error"}[scheduler_status]
    sched_label = {"active": f"Active  ·  {scheduler_jobs} jobs", "idle": "Idle", "stopped": "Stopped", "not_configured": "Not configured", "unknown": "Unknown"}[scheduler_status]
    st.markdown(f"""
<div class="sp-section">
    <div class="sp-row">
        <div class="sp-dot" style="background: var(--{sched_color});"></div>
        <span class="sp-label">Status</span>
        <span class="sp-value" style="color: var(--{sched_color});">{sched_label}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="sp-divider"></div>', unsafe_allow_html=True)

    # Tasks Section
    st.markdown('<div class="sp-header">Tasks</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="sp-section">
    <div class="sp-stat">
        <span class="sp-stat-label">Total tasks</span>
        <span class="sp-stat-value">{total_tasks}</span>
    </div>
    <div class="sp-stat">
        <span class="sp-stat-label">Enabled</span>
        <span class="sp-stat-value" style="color: var(--success);">{enabled_tasks}</span>
    </div>
    <div class="sp-stat">
        <span class="sp-stat-label">Disabled</span>
        <span class="sp-stat-value" style="color: var(--muted);">{total_tasks - enabled_tasks}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # Last run
    if stats.get("last_run_time"):
        import datetime
        try:
            dt = datetime.datetime.fromisoformat(stats["last_run_time"])
            from datetime import timezone
            dt_utc = dt.replace(tzinfo=timezone.utc)
            now = datetime.datetime.now(timezone.utc)
            delta = now - dt_utc
            if delta.days > 0:
                last_run_str = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                last_run_str = f"{delta.seconds // 3600}h ago"
            else:
                last_run_str = f"{max(1, delta.seconds // 60)}m ago"
        except Exception:
            last_run_str = stats["last_run_time"][:10]

        st.markdown(f"""
<div class="sp-divider"></div>
<div class="sp-header">Last Run</div>
<div class="sp-section">
    <div class="sp-row">
        <span class="sp-label">{stats.get('last_run_task', '—')}</span>
    </div>
    <div class="sp-row">
        <div class="sp-dot" style="background: var(--text-muted);"></div>
        <span class="sp-value" style="color: var(--text-muted);">{last_run_str}</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # Success rate
    total_runs = stats.get("total_runs", 0)
    success_runs = stats.get("success_runs", 0)
    if total_runs > 0:
        rate = int(success_runs / total_runs * 100)
        st.markdown(f"""
<div class="sp-divider"></div>
<div class="sp-header">Performance</div>
<div class="sp-section">
    <div class="sp-stat">
        <span class="sp-stat-label">Total runs</span>
        <span class="sp-stat-value">{total_runs}</span>
    </div>
    <div class="sp-stat">
        <span class="sp-stat-label">Success rate</span>
        <span class="sp-stat-value" style="color: {'#22c55e' if rate >= 80 else '#f59e0b' if rate >= 50 else '#ef4444'};">{rate}%</span>
    </div>
</div>
""", unsafe_allow_html=True)
