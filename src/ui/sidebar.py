"""
sidebar.py — Persistent left navigation sidebar.
Primary nav:   AI Copilot, Analytics, Reports, Predictions, Settings
Secondary nav: Home, Logs  (less prominent, always reachable)
Bottom:        Copilot status indicator + user card
"""
import streamlit as st
from session import navigate_to


@st.cache_data(ttl=30)
def _get_sys_status() -> tuple[dict, dict]:
    from services.database_service import get_database_status
    from services.copilot_service  import get_ai_status
    return get_database_status(), get_ai_status()


_PRIMARY_NAV = [
    ("💬", "AI Copilot"),
    ("📊", "Analytics"),
    ("📄", "Reports"),
    ("🎯", "Predictions"),
    ("⚙️", "Settings"),
]

_SECONDARY_NAV = [
    ("🏠", "Home"),
    ("📋", "Logs"),
]


def _nav_button(icon: str, label: str, current: str, secondary: bool = False):
    """Render a nav button. Active item highlighted with CSS class via st.button type."""
    is_active = current == label
    btn_type  = "primary" if is_active else "secondary"
    display   = f"{icon}  {label}"

    if st.button(display, key=f"nav_{label}", use_container_width=True, type=btn_type):
        navigate_to(label)
        st.rerun()


def render_sidebar():
    """Render the full left sidebar."""
    with st.sidebar:

        # ── Logo block ────────────────────────────────────────────────────────
        st.markdown("""
        <div class="sb-logo">
            <div class="sb-logo-icon">E</div>
            <div>
                <div class="sb-logo-text">Enterprise Copilot</div>
                <div class="sb-logo-sub">Profit Intelligence Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Primary nav ───────────────────────────────────────────────────────
        st.markdown('<div class="sb-section-label">Navigation</div>',
                    unsafe_allow_html=True)

        current = st.session_state.current_page
        for icon, label in _PRIMARY_NAV:
            _nav_button(icon, label, current)

        # ── Secondary nav ─────────────────────────────────────────────────────
        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section-label">Other</div>',
                    unsafe_allow_html=True)

        for icon, label in _SECONDARY_NAV:
            _nav_button(icon, label, current, secondary=True)

        # ── Copilot status ────────────────────────────────────────────────────
        st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

        try:
            db_status, ai_status = _get_sys_status()
            ai_ready = ai_status.get("ready", False)
            db_ok    = db_status.get("connected", False)
            model    = ai_status.get("model", "—")
            latency  = db_status.get("latency_ms", 0)

            ai_dot  = "" if ai_ready else "offline"
            db_dot  = "" if db_ok    else "offline"
            ai_text = "Online" if ai_ready else "Offline"
            db_text = f"DB · {latency}ms" if db_ok else "DB · Disconnected"

            st.markdown(f"""
            <div class="sb-status-card">
                <div class="sb-status-row" style="margin-bottom:6px;">
                    <div class="sb-status-dot {ai_dot}"></div>
                    <div>
                        <span class="sb-status-label">Copilot </span>
                        <span>{ai_text}</span>
                    </div>
                </div>
                <div class="sb-status-row">
                    <div class="sb-status-dot {db_dot}"></div>
                    <div style="font-size:0.72rem;color:#64748b;">{model} · {db_text}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        except Exception:
            pass

        # ── User card ─────────────────────────────────────────────────────────
        session_id = st.session_state.get("session_id", "—")
        chat_count = len([m for m in st.session_state.get("chat_history", [])
                          if m.get("role") == "user"])
        st.markdown(f"""
        <div class="sb-user-card">
            <div class="sb-user-avatar">A</div>
            <div>
                <div class="sb-user-name">Analyst</div>
                <div class="sb-user-role">Session {session_id} · {chat_count} quer{"y" if chat_count==1 else "ies"}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
