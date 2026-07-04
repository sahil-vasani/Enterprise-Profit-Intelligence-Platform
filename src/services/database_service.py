"""
database_service.py - Abstraction layer for database interactions.
"""
import time
import pandas as pd
from copilot.database import test_connection, execute_dataframe, execute_scalar

def get_database_status() -> dict:
    """Returns database connection status and latency."""
    start = time.perf_counter()
    is_connected = test_connection()
    latency = round((time.perf_counter() - start) * 1000, 2) if is_connected else 0
    return {
        "connected": is_connected,
        "latency_ms": latency
    }

def get_df(sql: str, fallback_df: pd.DataFrame = None) -> pd.DataFrame:
    """Executes a SQL query and returns a DataFrame, with optional fallback."""
    try:
        df = execute_dataframe(sql)
        if df.empty and fallback_df is not None:
            return fallback_df
        return df
    except Exception:
        if fallback_df is not None:
            return fallback_df
        return pd.DataFrame()

def get_kpi(sql: str, default: str) -> str:
    """Executes a SQL query for a single KPI value and formats it."""
    try:
        val = execute_scalar(sql)
        if val is None: return default
        if isinstance(val, (int, float)):
            if val > 10000000: return f"₹{val/10000000:.2f} Cr"
            if val > 100000: return f"₹{val/100000:.2f} Lakh"
            if val > 1000000: return f"${val/1000000:.2f}M"
            if val > 1000: return f"${val/1000:.1f}K"
            return f"{val:,.0f}"
        return str(val)
    except Exception:
        return default
