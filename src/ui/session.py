"""
session.py — Streamlit session state initialisation.
"""
import streamlit as st
import uuid


def init_session_state():
    """Initialize necessary Streamlit session state variables."""

    # Default landing page is the AI Copilot
    if "current_page" not in st.session_state:
        st.session_state.current_page = "AI Copilot"

    # Each message dict has:
    #   {"role": "user"|"assistant", "content": str}
    #   plus optional keys on assistant messages:
    #   "chart_data"    — plotly.io.to_json() string
    #   "table_data"    — list[dict] (≤10 rows)
    #   "chart_insight" — one-sentence insight string
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]

    if "user_settings" not in st.session_state:
        st.session_state.user_settings = {
            "theme": "light",
            "notifications": True,
        }


def navigate_to(page_name: str):
    """Update the current page in session state."""
    st.session_state.current_page = page_name
