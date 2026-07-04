"""
styles.py — Global CSS for the Enterprise Profit Intelligence Platform.
Design: Minimal ChatGPT/Claude style — white panel, light gray background,
blue accent (#2563eb), Inter font, generous whitespace.
"""
import streamlit as st


def load_css():
    st.markdown("""
    <style>
    /* ── Google Fonts ──────────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global reset ──────────────────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #f0f4f8 !important;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    header    { visibility: hidden; }
    footer    { visibility: hidden; }

    /* Main content area */
    .block-container {
        padding: 1.5rem 2rem 4rem 2rem !important;
        max-width: 900px !important;
        margin: 0 auto !important;
    }

    /* ── Sidebar ────────────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
        min-width: 260px !important;
        max-width: 260px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 0 !important;
    }

    /* ── Sidebar: logo block ────────────────────────────────────────────────── */
    .sb-logo {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 20px 16px 16px 16px;
        border-bottom: 1px solid #f1f5f9;
    }
    .sb-logo-icon {
        width: 36px; height: 36px;
        background: #2563eb;
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        color: white; font-size: 18px; font-weight: 700;
        flex-shrink: 0;
    }
    .sb-logo-text { font-size: 0.85rem; font-weight: 600; color: #1e293b; line-height: 1.3; }
    .sb-logo-sub  { font-size: 0.7rem; color: #94a3b8; font-weight: 400; }

    /* ── Sidebar: section label ─────────────────────────────────────────────── */
    .sb-section-label {
        font-size: 0.65rem;
        font-weight: 600;
        color: #94a3b8;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 16px 16px 6px 16px;
    }

    /* ── Sidebar: nav buttons ──────────────────────────────────────────────── */
    /* Inactive nav items (secondary type) */
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        border-radius: 8px !important;
        border: none !important;
        background: transparent !important;
        color: #475569 !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        text-align: left !important;
        padding: 8px 12px !important;
        justify-content: flex-start !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: #f8fafc !important;
        color: #1e293b !important;
        border: none !important;
    }

    /* Active nav item (primary type) */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        border-radius: 8px !important;
        border: none !important;
        border-left: 3px solid #2563eb !important;
        background: #eff6ff !important;
        color: #2563eb !important;
        font-size: 0.875rem !important;
        font-weight: 600 !important;
        text-align: left !important;
        padding: 8px 12px !important;
        justify-content: flex-start !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: #dbeafe !important;
    }

    /* Remove default margin between sidebar buttons */
    [data-testid="stSidebar"] .stButton {
        margin-bottom: 2px !important;
    }

    /* ── Sidebar: divider ───────────────────────────────────────────────────── */
    .sb-divider {
        height: 1px;
        background: #f1f5f9;
        margin: 8px 16px;
    }

    /* ── Sidebar: status card ───────────────────────────────────────────────── */
    .sb-status-card {
        margin: 8px 12px;
        padding: 10px 12px;
        background: #f8fafc;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .sb-status-row {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.78rem;
        color: #475569;
    }
    .sb-status-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #10b981;
        flex-shrink: 0;
    }
    .sb-status-dot.offline { background: #ef4444; }
    .sb-status-label { font-weight: 500; color: #1e293b; }

    /* ── Sidebar: user card ─────────────────────────────────────────────────── */
    .sb-user-card {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        border-top: 1px solid #f1f5f9;
        margin-top: auto;
    }
    .sb-user-avatar {
        width: 32px; height: 32px;
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        color: white; font-size: 0.8rem; font-weight: 600;
        flex-shrink: 0;
    }
    .sb-user-name  { font-size: 0.82rem; font-weight: 600; color: #1e293b; }
    .sb-user-role  { font-size: 0.72rem; color: #94a3b8; }

    /* ── Copilot Page ───────────────────────────────────────────────────────── */

    /* Greeting */
    .cop-greeting-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
        margin-top: 8px;
    }
    .cop-greeting-sub {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 28px;
    }

    /* Suggestion pills */
    .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 24px;
    }

    /* Chat container */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-bottom: 16px;
    }

    /* User bubble */
    .chat-user-wrap {
        display: flex;
        justify-content: flex-end;
    }
    .chat-user-bubble {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 18px 18px 4px 18px;
        padding: 10px 16px;
        max-width: 72%;
        font-size: 0.9rem;
        color: #1e293b;
        line-height: 1.5;
    }

    /* Assistant area */
    .chat-asst-wrap {
        display: flex;
        align-items: flex-start;
        gap: 10px;
    }
    .chat-asst-avatar {
        width: 32px; height: 32px;
        background: #2563eb;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        color: white; font-size: 0.85rem; font-weight: 700;
        flex-shrink: 0;
        margin-top: 2px;
    }
    .chat-asst-content {
        flex: 1;
        min-width: 0;
    }
    .chat-asst-text {
        font-size: 0.9rem;
        color: #1e293b !important;
        line-height: 1.6;
        margin-bottom: 12px;
    }

    /* Insight callout */
    .insight-callout {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-left: 4px solid #10b981;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.85rem;
        color: #14532d !important;
        margin-top: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .insight-icon { font-size: 1rem; flex-shrink: 0; }
    .insight-text { color: #14532d !important; }

    /* KPI callout — for single-row query results */
    .kpi-callout {
        background: white;
        border: 1px solid #bfdbfe;
        border-left: 4px solid #2563eb;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 8px 0 12px 0;
        display: inline-block;
        min-width: 160px;
    }
    .kpi-callout-title {
        font-size: 0.72rem;
        font-weight: 600;
        color: #64748b !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }
    .kpi-callout-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2563eb !important;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .kpi-callout-label {
        font-size: 0.8rem;
        color: #475569 !important;
        margin-top: 4px;
    }
    .kpi-callout-sublabel {
        font-weight: 600;
        color: #1e293b !important;
    }

    /* Thinking spinner */
    .thinking-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #94a3b8;
        font-size: 0.85rem;
        font-style: italic;
        padding: 8px 0;
    }

    /* ── Disclaimer ─────────────────────────────────────────────────────────── */
    .cop-disclaimer {
        text-align: center;
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 6px;
    }

    /* ── Generic page header ────────────────────────────────────────────────── */
    .page-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .page-subtitle {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 24px;
    }

    /* ── KPI metric card ────────────────────────────────────────────────────── */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
        transition: box-shadow 0.2s;
    }
    .metric-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .metric-title {
        font-size: 0.78rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 2px;
    }
    .metric-delta { font-size: 0.82rem; font-weight: 500; }
    .delta-positive { color: #10b981; }
    .delta-negative { color: #ef4444; }

    /* ── Stframe tables ─────────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        overflow: hidden !important;
    }

    /* ── Plotly charts ──────────────────────────────────────────────────────── */
    [data-testid="stPlotlyChart"] {
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        background: white;
    }

    /* ── Buttons ────────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 20px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        padding: 6px 14px !important;
        border: 1px solid #e2e8f0 !important;
        background: white !important;
        color: #475569 !important;
        transition: border-color 0.15s, color 0.15s, background 0.15s !important;
    }
    .stButton > button:hover {
        border-color: #2563eb !important;
        color: #2563eb !important;
        background: #eff6ff !important;
    }

    /* Chat input */
    [data-testid="stChatInput"] {
        border-radius: 24px !important;
    }
    [data-testid="stChatInput"] > div {
        border-radius: 24px !important;
        border: 1px solid #e2e8f0 !important;
        background: white !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        color: #1e293b !important;
        font-size: 0.9rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
