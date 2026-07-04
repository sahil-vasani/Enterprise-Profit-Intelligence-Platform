import streamlit as st
import os

# ── Page config must be the very first Streamlit call ─────────────────────────
st.set_page_config(
    page_title="Enterprise Profit Intelligence Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
# COPILOT_DIR first so copilot/utils.py is found before analytics/utils.py
ROOT_DIR    = Path(__file__).resolve().parent.parent.parent
COPILOT_DIR = ROOT_DIR / "src" / "copilot"
SRC_DIR     = ROOT_DIR / "src"

if str(COPILOT_DIR) not in sys.path:
    sys.path.insert(0, str(COPILOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

from styles   import load_css
from session  import init_session_state
from sidebar  import render_sidebar
from components import (
    render_copilot,
    render_analytics,
    render_forecast,
    render_reports,
    render_settings,
    render_home,
    render_logs,
)

# ── Warm-up singletons (LangGraph workflow + schema cache) ────────────────────
from services.copilot_service import _get_workflow
_get_workflow()

# Flat import so schema_cache module object is shared with all copilot services
from src.copilot.schema_cache import load_schema_cache
load_schema_cache()


# ── Page router ───────────────────────────────────────────────────────────────
_ROUTER = {
    "AI Copilot":  render_copilot,
    "Analytics":   render_analytics,
    "Reports":     render_reports,
    "Predictions": render_forecast,
    "Settings":    render_settings,
    "Home":        render_home,
    "Logs":        render_logs,
}


def main():
    """Main entry point for the Streamlit UI."""
    load_css()
    init_session_state()
    render_sidebar()

    page = st.session_state.current_page
    render_fn = _ROUTER.get(page, render_copilot)
    render_fn()


if __name__ == "__main__":
    main()
