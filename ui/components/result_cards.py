"""Result card component for displaying formatted task results."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

import streamlit as st

# Import the shared utility for cleaning raw HTML/JSON from LLM responses
from ui.shared import clean_result_text, escape_html


def _relative_time(iso_timestamp: Optional[str]) -> str:
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


def _get_sentiment_emoji(sentiment: str) -> str:
    s = (sentiment or "").lower()
    if "positive" in s or "bullish" in s or "buy" in s:
        return "🟢", "Positive", "badge-success"
    elif "negative" in s or "bearish" in s or "sell" in s or "pause" in s:
        return "🔴", "Negative", "badge-error"
    elif "mixed" in s:
        return "🟡", "Mixed", "badge-warning"
    elif "neutral" in s:
        return "⚪", "Neutral", "badge-muted"
    return "⚪", "Unknown", "badge-muted"


def _get_status_badge(status: str) -> tuple[str, str]:
    s = (status or "").lower()
    if s in ("success", "completed"):
        return "Success", "badge-success"
    elif s in ("error", "failed"):
        return "Error", "badge-error"
    elif s == "running":
        return "Running", "badge-running"
    return str(status or "Unknown").title(), "badge-muted"


def _render_metric_value(key: str, value: Any) -> str:
    """Format a key-metric pair for display."""
    # Numeric price
    if isinstance(value, (int, float)) and ("price" in key or "value" in key or "cost" in key):
        if value >= 1000:
            return f"${value:,.0f}"
        return f"{value:.2f}"
    # Percentage
    if isinstance(value, (int, float)) and ("percent" in key or "change" in key):
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    # Boolean
    if isinstance(value, bool):
        return "Yes" if value else "No"
    # String
    return str(value)[:80]


def _render_tool_outputs_card(tool_outputs: Dict[str, Any]) -> str:
    """Render tool outputs as a formatted card."""
    if not tool_outputs or "steps" not in tool_outputs:
        return ""

    steps = tool_outputs.get("steps", [])
    if not steps:
        return ""

    parts = []
    for step in steps:
        tool = step.get("tool", "unknown")
        result = step.get("result")
        error = step.get("error")

        if error:
            parts.append(f'<div style="margin-bottom:8px;"><span class="tool-chip" style="background:var(--error-dim);color:var(--error);border-color:rgba(239,68,68,0.3);">{escape_html(tool)}</span> <span style="font-size:12px;color:var(--error);">Error: {escape_html(error[:60])}</span></div>')
            continue

        if not result:
            continue

        # Crypto price: show price + change prominently
        if tool == "crypto_price" and isinstance(result, dict):
            price = result.get("price")
            change = result.get("change_24h")
            if price is not None:
                price_str = f"${price:,.0f}" if isinstance(price, (int, float)) else str(price)
                change_str = f"{change:+.2f}%" if isinstance(change, (int, float)) else ""
                change_color = "var(--success)" if (isinstance(change, (int, float)) and change >= 0) else "var(--error)"
                parts.append(f"""
                <div class="output-metric">
                    <div class="output-metric-label">{tool}</div>
                    <div style="display:flex;align-items:baseline;gap:12px;">
                        <span class="output-metric-value" style="font-size:22px;font-weight:700;">{price_str}</span>
                        {f'<span style="font-size:14px;color:{change_color};font-weight:600;">{change_str}</span>' if change_str else ''}
                    </div>
                </div>""")

        # News items: show headlines
        elif tool in ("crypto_news", "news_search", "rss_reader") and isinstance(result, dict):
            items = result.get("items", [])
            if items:
                headlines = []
                for item in items[:3]:
                    title = item.get("title", "")[:70]
                    if title:
                        headlines.append(f'<div style="margin-bottom:6px;padding:6px 8px;background:var(--bg-tertiary);border-radius:var(--radius-sm);border-left:3px solid var(--accent);"><span style="font-size:12px;color:var(--text-primary);line-height:1.4;">{escape_html(title)}{"..." if len(item.get("title","")) > 70 else ""}</span></div>')
                if headlines:
                    parts.append(f"""
                    <div style="margin-bottom:8px;">
                        <span class="tool-chip">{escape_html(tool)}</span>
                        <div style="margin-top:6px;">{''.join(headlines)}</div>
                    </div>""")

        # market_sentiment
        elif tool == "market_sentiment" and isinstance(result, dict):
            score = result.get("score")
            label = result.get("label", "")
            if score is not None or label:
                parts.append(f"""
                <div class="output-metric">
                    <div class="output-metric-label">{tool}</div>
                    <span class="output-metric-value" style="font-size:15px;">{label or str(score)}</span>
                </div>""")

        # hn_top / github_search
        elif tool in ("hn_top", "github_search", "arxiv_search") and isinstance(result, dict):
            items = result.get("items", result.get("repos", []))
            if items:
                top_items = []
                for item in items[:3]:
                    title = item.get("title", item.get("name", ""))[:60]
                    if title:
                        top_items.append(f'<div style="font-size:12px;color:var(--text-secondary);padding:3px 0;border-bottom:1px solid var(--border);">• {escape_html(title)}</div>')
                if top_items:
                    parts.append(f"""
                    <div style="margin-bottom:8px;">
                        <span class="tool-chip">{escape_html(tool)}</span>
                        <div style="margin-top:4px;">{''.join(top_items)}</div>
                    </div>""")

    return "\n".join(parts)


def _render_key_metrics(key_metrics: Union[Dict, list]) -> str:
    """Render key metrics as a row of metric pills."""
    if not key_metrics:
        return ""

    parts = []

    if isinstance(key_metrics, dict):
        for key, value in key_metrics.items():
            formatted_value = _render_metric_value(key, value)
            display_key = key.replace("_", " ").title()
            parts.append(f"""
            <div class="key-metric-pill">
                <div class="key-metric-label">{escape_html(display_key)}</div>
                <div class="key-metric-value">{escape_html(formatted_value)}</div>
            </div>""")

    elif isinstance(key_metrics, list):
        for metric in key_metrics:
            if isinstance(metric, dict):
                name = metric.get("name", metric.get("label", "Metric"))
                impact = metric.get("impact", "")
                status = metric.get("status", "")
                val = f"{impact} — {status}" if (impact or status) else str(metric)
                parts.append(f"""
                <div class="key-metric-pill">
                    <div class="key-metric-label">{escape_html(name)}</div>
                    <div class="key-metric-value">{escape_html(val)}</div>
                </div>""")

    if not parts:
        return ""

    return f'<div class="key-metrics-row">{"".join(parts)}</div>'


def render_result_card(row: Dict[str, Any], show_task_name: bool = True) -> None:
    """
    Render a beautifully formatted result card.

    Layout:
      [Header: task name + status badge + time]
      [Hero: summary in large text + sentiment/recommendation in colored blocks]
      [Key Metrics: row of data pills]
      [Tool Outputs: formatted news headlines / prices / scores]
    """
    task_name = row.get("name", "Unknown Task")
    status = row.get("status", "")
    finished_at = row.get("finished_at")
    status_label, status_class = _get_status_badge(status)
    time_str = _relative_time(finished_at)

    # Parse result_json
    result_json = None
    if row.get("result_json"):
        try:
            result_json = json.loads(row["result_json"])
        except json.JSONDecodeError:
            pass

    summary = clean_result_text((result_json.get("summary") if result_json else None) or row.get("result_text", ""))
    sentiment = clean_result_text(result_json.get("sentiment") if result_json else None)
    recommendation = clean_result_text(result_json.get("recommendation") if result_json else None)
    rationale = clean_result_text(result_json.get("rationale") if result_json else None)
    key_metrics = result_json.get("key_metrics") if result_json else None
    tool_outputs = None
    if row.get("tool_outputs_json"):
        try:
            tool_outputs = json.loads(row["tool_outputs_json"])
        except json.JSONDecodeError:
            pass

    emoji, sentiment_label, sentiment_class = _get_sentiment_emoji(sentiment)
    # Escape text content for safe HTML embedding
    safe_summary = escape_html(summary) if summary else ""
    safe_sentiment = escape_html(sentiment) if sentiment else ""
    safe_recommendation = escape_html(recommendation) if recommendation else ""
    safe_rationale = escape_html(rationale) if rationale else ""

    # ── Header ──────────────────────────────────────────
    st.markdown(f"""
    <div class="result-card">
        <div class="result-card-header">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <span style="font-size:15px;font-weight:700;color:var(--text-primary);">{task_name}</span>
                <span class="badge {status_class}">{status_label}</span>
            </div>
            <div style="display:flex;align-items:center;gap:10px;">
                <span style="font-size:12px;color:var(--text-muted);">{time_str}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Hero Summary ────────────────────────────────────
    if summary:
        st.markdown(f"""
        <div class="result-hero">
            <div class="result-hero-summary">{safe_summary}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Sentiment + Recommendation ───────────────────────
    # Use Streamlit-native components for text content (more reliable than HTML)
    if sentiment or recommendation:
        c1, c2 = st.columns([1, 1])
        with c1:
            if sentiment:
                emoji, label, cls = _get_sentiment_emoji(sentiment)
                st.markdown(f"**{emoji} Sentiment**")
                st.markdown(f'<span class="badge {cls}">{escape_html(label)}</span>', unsafe_allow_html=True)
                st.caption(safe_sentiment)
        with c2:
            if recommendation:
                st.markdown("**&#128203; Recommendation**")
                st.success(safe_recommendation)

    # ── Key Metrics ──────────────────────────────────────
    metrics_html = _render_key_metrics(key_metrics)
    if metrics_html:
        st.markdown(f"""
        <div class="result-metrics-section">
            <div class="result-section-label">📊 Key Metrics</div>
            {metrics_html}
        </div>
        """, unsafe_allow_html=True)

    # ── Tool Outputs ─────────────────────────────────────
    if tool_outputs:
        outputs_html = _render_tool_outputs_card(tool_outputs)
        if outputs_html:
            with st.expander("🔍 Tool Outputs", expanded=False):
                st.markdown(outputs_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_results_grid(
    results: list[Dict[str, Any]],
    max_visible: int = 6,
) -> None:
    if not results:
        st.info("No results yet. Run a task to see results here.")
        return

    visible = results[:max_visible]
    cols = st.columns(2) if len(visible) > 1 else [1]
    for idx, row in enumerate(visible):
        with cols[idx % len(cols)]:
            render_result_card(row)
            st.markdown("")


def render_result_detail(row: Dict[str, Any]) -> None:
    """Render a detailed single result view with all fields."""
    task_name = row.get("name", "Unknown Task")
    status = row.get("status", "")
    finished_at = row.get("finished_at")
    status_label, status_class = _get_status_badge(status)
    time_str = _relative_time(finished_at)

    result_json = None
    if row.get("result_json"):
        try:
            result_json = json.loads(row["result_json"])
        except json.JSONDecodeError:
            pass

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"#### {task_name}")
    with col2:
        st.markdown(
            f"<div style='text-align:right;'><span class='badge {status_class}'>{status_label}</span>"
            f"  <span style='font-size:12px;color:var(--text-muted);margin-left:8px;'>{time_str}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Clean the raw result fields before displaying
    clean_summary = clean_result_text(result_json.get("summary") if result_json else None) if result_json else None
    clean_sentiment = clean_result_text(result_json.get("sentiment") if result_json else None) if result_json else None
    clean_recommendation = clean_result_text(result_json.get("recommendation") if result_json else None) if result_json else None
    clean_rationale = clean_result_text(result_json.get("rationale") if result_json else None) if result_json else None

    if result_json:
        # Summary in a hero box
        if clean_summary:
            st.markdown("**Summary**")
            st.info(clean_summary)
            st.divider()

        # Sentiment + Recommendation
        c1, c2 = st.columns([1, 1])
        with c1:
            if clean_sentiment:
                emoji, label, cls = _get_sentiment_emoji(clean_sentiment)
                st.markdown(f"**{emoji} Sentiment**")
                st.markdown(f'<span class="badge {cls}" style="font-size:14px;">{escape_html(label)}</span>', unsafe_allow_html=True)
                st.caption(clean_sentiment)
        with c2:
            if clean_recommendation:
                st.markdown("**📋 Recommendation**")
                st.success(clean_recommendation)
        if clean_sentiment or clean_recommendation:
            st.divider()

        # Key Metrics
        km = result_json.get("key_metrics")
        if km:
            st.markdown("**📊 Key Metrics**")
            if isinstance(km, dict):
                for k, v in km.items():
                    formatted = _render_metric_value(k, v)
                    col_m1, col_m2 = st.columns([1, 2])
                    with col_m1:
                        st.markdown(f"**{k.replace('_', ' ').title()}**")
                    with col_m2:
                        st.markdown(formatted)
            elif isinstance(km, list):
                for m in km:
                    if isinstance(m, dict):
                        name = m.get("name", m.get("label", "Metric"))
                        val = " | ".join(f"{kk}: `{vv}`" for kk, vv in m.items() if vv)
                        st.markdown(f"**{name}** — {val}")
            st.divider()

        # Rationale
        if clean_rationale:
            st.markdown("**💡 Rationale**")
            st.caption(clean_rationale)
            st.divider()

    elif row.get("result_text"):
        st.markdown("**Result**")
        st.markdown(clean_result_text(row["result_text"]))
        st.divider()

    # Tool outputs in collapsible section
    if row.get("tool_outputs_json"):
        try:
            tool_outputs = json.loads(row["tool_outputs_json"])
            with st.expander("🔍 Tool Outputs (Raw Data)"):
                st.json(tool_outputs)
        except json.JSONDecodeError:
            st.text(row["tool_outputs_json"])

    # Plan
    if row.get("plan_json"):
        try:
            plan = json.loads(row["plan_json"])
            with st.expander("📋 Execution Plan"):
                st.json(plan)
        except json.JSONDecodeError:
            st.text(row["plan_json"])
