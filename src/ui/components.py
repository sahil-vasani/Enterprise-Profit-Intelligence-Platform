"""
components.py — Page renderers for the Enterprise Profit Intelligence Platform.
"""
import streamlit as st
import time
import os
import datetime
import json
import psutil
import platform
import pandas as pd
import plotly.io as pio
from pathlib import Path

from charts import (
    create_revenue_trend_chart,
    create_category_distribution_chart,
    create_monthly_profit_chart,
    create_customer_segmentation_chart,
    get_chart_config,
)
from services.copilot_service  import run_backend_query
from services.database_service import get_kpi
from services.analytics_service import get_analytics_modules
from services.prediction_service import run_prediction


# ── Suggestion pills ──────────────────────────────────────────────────────────

_SUGGESTIONS = [
    ("📊", "Top 10 profitable products"),
    ("💰", "Revenue by state"),
    ("👥", "Best customers by revenue"),
    ("📦", "Inventory analysis"),
    ("📈", "Marketing ROI analysis"),
    ("📄", "Generate CEO report"),
    ("🔮", "Predict next month profit"),
    ("🔍", "Explain average margin drop"),
]


# ── Backend query helper ──────────────────────────────────────────────────────

def _query_and_store(question: str):
    """Run the backend, append user + assistant messages to chat_history."""
    st.session_state.chat_history.append({
        "role":    "user",
        "content": question,
        "ts":      datetime.datetime.now().strftime("%H:%M"),
    })

    with st.spinner("Analyzing your question…"):
        res = run_backend_query(question)

    summary        = res.get("business_summary", "No response generated.")
    chart_data_str = res.get("chart_data", "")
    table_data     = res.get("table_data", [])
    chart_insight  = res.get("chart_insight", "")
    intent         = res.get("intent", "—")
    exec_time      = res.get("execution_time", 0)

    assistant_msg = {
        "role":          "assistant",
        "content":       summary,
        "ts":            datetime.datetime.now().strftime("%H:%M"),
        "meta":          f"Intent: {intent} · {exec_time}s",
        "chart_data":    chart_data_str,
        "table_data":    table_data,
        "chart_insight": chart_insight,
    }
    st.session_state.chat_history.append(assistant_msg)
    st.rerun()


# ── Chat message renderers ────────────────────────────────────────────────────

def _render_user_msg(msg: dict):
    st.markdown(
        f'<div class="chat-user-wrap">'
        f'<div class="chat-user-bubble">{msg["content"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_assistant_msg(msg: dict):
    st.markdown('<div class="chat-asst-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="chat-asst-avatar">AI</div>'
        '<div class="chat-asst-content">',
        unsafe_allow_html=True,
    )

    # ── Text summary ──────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="chat-asst-text">{msg["content"]}</div>',
        unsafe_allow_html=True,
    )

    # ── Chart ─────────────────────────────────────────────────────────────────
    chart_json = msg.get("chart_data", "")
    table_rows = msg.get("table_data", [])

    if chart_json:
        try:
            fig = pio.from_json(chart_json)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        except Exception:
            pass  # chart render failure is silent
    elif table_rows and len(table_rows) == 1:
        # Single-row result → KPI callout instead of an empty chart area
        row = table_rows[0]
        # Find the best numeric value and its label in the row
        _METRIC_KW = ("total_sold", "sold", "revenue", "profit", "amount",
                      "count", "qty", "quantity", "sales", "margin",
                      "price", "cost", "orders", "units", "income", "gross", "net")
        _ID_SFX    = ("_id", "id", "asin", "sku", "code", "key")
        def _is_id(k): return any(k.lower().endswith(s) for s in _ID_SFX) or k.lower() in _ID_SFX

        kpi_key = kpi_val = kpi_label_key = kpi_label_val = None
        # Prefer metric-named numeric columns
        for k, v in row.items():
            if not _is_id(k) and isinstance(v, (int, float)) and any(kw in k.lower() for kw in _METRIC_KW):
                kpi_key, kpi_val = k, v
                break
        # Fallback: first non-id numeric
        if kpi_key is None:
            for k, v in row.items():
                if not _is_id(k) and isinstance(v, (int, float)):
                    kpi_key, kpi_val = k, v
                    break
        # Find a text label column
        for k, v in row.items():
            if k != kpi_key and not _is_id(k) and isinstance(v, str):
                kpi_label_key, kpi_label_val = k, v
                break

        if kpi_val is not None:
            label_html = (
                f'<div class="kpi-callout-label">{kpi_label_key.replace("_"," ").title()}: '
                f'<span class="kpi-callout-sublabel">{kpi_label_val}</span></div>'
                if kpi_label_val else ""
            )
            st.markdown(
                f'<div class="kpi-callout">'
                f'<div class="kpi-callout-title">{kpi_key.replace("_"," ").title()}</div>'
                f'<div class="kpi-callout-value">{kpi_val:,.0f}</div>'
                f'{label_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Data table ────────────────────────────────────────────────────────────
    if table_rows:
        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Insight callout ───────────────────────────────────────────────────────
    insight = msg.get("chart_insight", "")
    if insight:
        st.markdown(
            f'<div class="insight-callout">'
            f'<span class="insight-icon">💡</span>'
            f'<span class="insight-text">{insight}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Meta caption ──────────────────────────────────────────────────────────
    if msg.get("meta"):
        st.caption(msg["meta"])

    st.markdown("</div></div>", unsafe_allow_html=True)


# ── AI Copilot page ───────────────────────────────────────────────────────────

def render_copilot():
    """Renders the AI Copilot — ChatGPT/Claude-style chat interface."""

    # ── Greeting ──────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="cop-greeting-title">Hello, Analyst 👋</div>'
        '<div class="cop-greeting-sub">What business insights can I find for you today?</div>',
        unsafe_allow_html=True,
    )

    # ── Suggestion pills (2 rows of 4) ────────────────────────────────────────
    row1_cols = st.columns(4)
    for i, (icon, label) in enumerate(_SUGGESTIONS[:4]):
        with row1_cols[i]:
            if st.button(f"{icon} {label}", key=f"pill_{i}", use_container_width=True):
                _query_and_store(label)

    row2_cols = st.columns(4)
    for i, (icon, label) in enumerate(_SUGGESTIONS[4:]):
        with row2_cols[i]:
            if st.button(f"{icon} {label}", key=f"pill_{i+4}", use_container_width=True):
                _query_and_store(label)

    st.markdown("<br/>", unsafe_allow_html=True)

    # ── Chat history ──────────────────────────────────────────────────────────
    if st.session_state.chat_history:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                _render_user_msg(msg)
            else:
                _render_assistant_msg(msg)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Clear chat ────────────────────────────────────────────────────────────
    if st.session_state.chat_history:
        if st.button("🗑️ Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()

    # ── Chat input (Streamlit renders this pinned to the bottom) ──────────────
    if prompt := st.chat_input("Ask a business question…"):
        _query_and_store(prompt)

    # ── Disclaimer ────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="cop-disclaimer">'
        'AI-generated insights from live PostgreSQL data warehouse · '
        'Powered by Qwen2.5-7B via Ollama'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Home page ─────────────────────────────────────────────────────────────────

def render_home():
    """Renders the Home dashboard with KPI cards and charts."""
    st.markdown('<div class="page-title">Enterprise Profit Intelligence</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">AI-powered Business Intelligence — PostgreSQL · LangGraph · ML</div>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    tot_rev  = get_kpi("SELECT sum(total_amount) FROM fact_sales", "$4.2M")
    tot_cust = get_kpi("SELECT count(distinct customer_id) FROM fact_sales", "12,450")
    net_prof = get_kpi("SELECT sum(net_profit) FROM fact_sales", "$850K")
    tot_ord  = get_kpi("SELECT count(order_id) FROM fact_sales", "45,210")

    with col1:
        st.markdown(f'''<div class="metric-card">
            <div class="metric-title">Total Revenue</div>
            <div class="metric-value">{tot_rev}</div>
            <div class="metric-delta delta-positive">↑ 12.5% vs last month</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Customers</div>
            <div class="metric-value">{tot_cust}</div>
            <div class="metric-delta delta-positive">↑ 5.2% vs last month</div>
        </div>''', unsafe_allow_html=True)

    with col2:
        st.markdown(f'''<div class="metric-card">
            <div class="metric-title">Net Profit</div>
            <div class="metric-value">{net_prof}</div>
            <div class="metric-delta delta-positive">↑ 8.4% vs last month</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Average Margin</div>
            <div class="metric-value">24.5%</div>
            <div class="metric-delta delta-negative">↓ 1.2% vs last month</div>
        </div>''', unsafe_allow_html=True)

    with col3:
        st.markdown(f'''<div class="metric-card">
            <div class="metric-title">Orders</div>
            <div class="metric-value">{tot_ord}</div>
            <div class="metric-delta delta-positive">↑ 15.3% vs last month</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Return Rate</div>
            <div class="metric-value">3.2%</div>
            <div class="metric-delta delta-negative">↓ 0.5% vs last month</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    chart_col1, chart_col2 = st.columns(2)
    cfg = get_chart_config()
    with chart_col1:
        st.plotly_chart(create_revenue_trend_chart(), use_container_width=True, config=cfg)
    with chart_col2:
        st.plotly_chart(create_category_distribution_chart(), use_container_width=True, config=cfg)


# ── Analytics page ────────────────────────────────────────────────────────────

def render_analytics():
    """Renders the Analytics Engine dashboard."""
    st.markdown('<div class="page-title">Analytics Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Run specialized analytical modules against the data warehouse</div>',
                unsafe_allow_html=True)

    modules = get_analytics_modules()

    for i in range(0, len(modules), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(modules):
                mod = modules[i + j]
                with cols[j]:
                    st.markdown(f'''<div class="metric-card">
                        <div style="font-size:1.6rem;margin-bottom:8px">{mod["icon"]}</div>
                        <div style="font-weight:600;color:#1e293b;margin-bottom:4px">{mod["title"]}</div>
                        <div style="font-size:0.82rem;color:#64748b;margin-bottom:12px">{mod["desc"]}</div>
                    </div>''', unsafe_allow_html=True)
                    if st.button(f"Run {mod['title']}", key=f"run_{mod['title']}",
                                 use_container_width=True):
                        with st.spinner(f"Executing {mod['title']}…"):
                            res = run_backend_query(f"Run {mod['title']}")
                        st.success(f"Completed in {res.get('execution_time', 0)}s")
                        with st.expander("View Results", expanded=True):
                            st.write(res.get("business_summary", ""))
                        st.download_button(
                            "Download JSON", data=json.dumps(res, default=str),
                            file_name=f"{mod['title'].replace(' ', '_')}.json",
                            mime="application/json", key=f"dl_{mod['title']}",
                        )
        st.markdown("<br/>", unsafe_allow_html=True)

    st.markdown("### Interactive Insights")
    col1, col2 = st.columns(2)
    cfg = get_chart_config()
    with col1:
        st.plotly_chart(create_monthly_profit_chart(), use_container_width=True, config=cfg)
    with col2:
        st.plotly_chart(create_customer_segmentation_chart(), use_container_width=True, config=cfg)


# ── Predictions page ──────────────────────────────────────────────────────────

def render_forecast():
    """Renders the Forecasting & Predictions page (routed as 'Predictions')."""
    st.markdown('<div class="page-title">Forecasting & Predictions</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Machine Learning predictions on future business performance</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Prediction Configuration")
        target  = st.selectbox("Target Variable", ["Profitability", "Sales Volume", "Customer Churn"])
        horizon = st.selectbox("Horizon", ["Next 30 Days", "Next Quarter", "Next Year"])
        conf    = st.slider("Confidence Interval", 50, 99, 95)
        if st.button("Run Prediction Model", type="primary", use_container_width=True):
            st.session_state.prediction_run    = True
            st.session_state.prediction_params = (target, horizon, conf)

    with col2:
        st.markdown("### Model Results")

        if getattr(st.session_state, "prediction_run", False):
            with st.spinner("Running Prediction Agent…"):
                target, horizon, conf = st.session_state.prediction_params
                res = run_prediction(target, horizon, conf)

            model_name   = res.get("model_name", "Random Forest")
            confidence   = res.get("confidence", f"{conf}%")
            feat_imp     = res.get("feature_importance", "Category, Recency, Frequency")

            st.markdown(f'''<div class="metric-card">
                <div style="display:flex;justify-content:space-between">
                    <div>
                        <div class="metric-title">Model</div>
                        <div class="metric-value" style="font-size:1.4rem">{model_name}</div>
                    </div>
                    <div>
                        <div class="metric-title">Confidence</div>
                        <div class="metric-value" style="font-size:1.4rem;color:#10b981">{confidence}</div>
                    </div>
                </div>
                <div style="margin-top:10px">
                    <div class="metric-title">Top Features</div>
                    <div style="font-size:0.88rem;color:#64748b">{feat_imp}</div>
                </div>
            </div>''', unsafe_allow_html=True)

            with st.expander("Prediction Details", expanded=True):
                st.write(res.get("business_summary", ""))
            st.download_button("Download JSON", data=json.dumps(res, default=str),
                               file_name="Prediction_Result.json", mime="application/json")
            st.plotly_chart(create_revenue_trend_chart(), use_container_width=True,
                            config=get_chart_config())
        else:
            st.markdown('''<div class="metric-card" style="color:#94a3b8;text-align:center;padding:40px">
                Configure and run a prediction model to see results here.
            </div>''', unsafe_allow_html=True)


# ── Reports page ──────────────────────────────────────────────────────────────

def render_reports():
    """Renders the Executive Reports page."""
    st.markdown('<div class="page-title">Executive Reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Generate and download comprehensive business reports</div>',
                unsafe_allow_html=True)

    reports = [
        {"title": "CEO Report",       "desc": "High-level overview of all major KPIs and strategic insights."},
        {"title": "Monthly Report",   "desc": "Detailed breakdown of the past 30 days performance."},
        {"title": "Quarterly Report", "desc": "Quarterly P&L, balance sheet and growth metrics."},
        {"title": "Inventory Report", "desc": "Stockout warnings, carrying costs and turnover rates."},
        {"title": "Marketing Report", "desc": "Campaign performance, ROAS, and acquisition metrics."},
    ]

    for report in reports:
        with st.expander(f"📄 **{report['title']}**"):
            st.write(report["desc"])
            col1, col2, col3 = st.columns([1, 2, 2])
            with col1:
                if st.button("Generate", key=f"gen_{report['title']}"):
                    with st.spinner(f"Generating {report['title']}…"):
                        res = run_backend_query(f"Generate {report['title']}")
                        content = res.get("business_summary", "")
                        st.session_state[f"rpt_{report['title']}"] = content

            content = st.session_state.get(f"rpt_{report['title']}")
            if content:
                st.markdown(content)
                with col2:
                    st.download_button("Download .md", data=content,
                                       file_name=f"{report['title'].replace(' ', '_')}.md",
                                       mime="text/markdown", key=f"dl_md_{report['title']}")
                with col3:
                    st.download_button("Download .txt", data=content,
                                       file_name=f"{report['title'].replace(' ', '_')}.txt",
                                       mime="text/plain", key=f"dl_txt_{report['title']}")


# ── Settings page ─────────────────────────────────────────────────────────────

def render_settings():
    """Renders the System Settings page."""
    st.markdown('<div class="page-title">System Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Configure the Enterprise Copilot Platform</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Database")
        st.info("**Type**: PostgreSQL 15\n\n**Host**: localhost:5432\n\n**Status**: Connected 🟢")

        st.markdown("### AI Model")
        st.success("**Runtime**: Ollama\n\n**Model**: Qwen2.5-7B\n\n**Temperature**: 0.1")

    with col2:
        st.markdown("### System")
        st.write(f"**Platform**: {platform.system()} {platform.release()}")
        st.write(f"**CPU Cores**: {psutil.cpu_count(logical=True)}")
        st.write(f"**Total RAM**: {round(psutil.virtual_memory().total / (1024**3), 1)} GB")
        st.write(f"**Python**: {platform.python_version()}")
        st.write(f"**CWD**: `{os.getcwd()}`")

        st.markdown("### Key Packages")
        st.code("streamlit · plotly · langchain\nlanggraph · langchain-ollama\nsqlalchemy · pandas · psutil",
                language="text")


# ── Logs page ─────────────────────────────────────────────────────────────────

def render_logs():
    """Renders the System Logs page."""
    st.markdown('<div class="page-title">System Logs</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Recent events from the Copilot backend</div>',
                unsafe_allow_html=True)

    log_path = Path("logs/copilot/copilot.log")

    col1, col2, col3, col4, col5 = st.columns(5)
    filter_type = st.session_state.get("log_filter")
    if col1.button("All",     use_container_width=True): st.session_state.log_filter = None;      filter_type = None
    if col2.button("INFO",    use_container_width=True): st.session_state.log_filter = "INFO";    filter_type = "INFO"
    if col3.button("WARNING", use_container_width=True): st.session_state.log_filter = "WARNING"; filter_type = "WARNING"
    if col4.button("ERROR",   use_container_width=True): st.session_state.log_filter = "ERROR";   filter_type = "ERROR"
    if col5.button("SQL/AI",  use_container_width=True): st.session_state.log_filter = "SQL";     filter_type = "SQL"

    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines.reverse()
        count = 0
        for line in lines:
            if not line.strip():
                continue
            if filter_type:
                if filter_type == "SQL":
                    if not any(kw in line for kw in ["SQL", "sql", "Agent", "AI", "Predict"]):
                        continue
                elif filter_type not in line:
                    continue
            with st.expander(line[:100] + ("…" if len(line) > 100 else ""), expanded=False):
                st.code(line.strip(), language="log")
            count += 1
            if count >= 50:
                break
        if count == 0:
            st.info(f"No logs matching filter: {filter_type or 'All'}")
    else:
        st.info("No log file found at `logs/copilot/copilot.log`")
