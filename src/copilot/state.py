"""
state.py — LangGraph state definition for the AI Business Copilot.
"""

from typing import Any
from typing_extensions import TypedDict


class CopilotState(TypedDict, total=False):
    """State object passed through every node in the LangGraph workflow."""

    # User input
    question: str

    # Router classification
    intent: str  # sql | analytics | prediction | report | general

    # Conversation
    messages: list[dict[str, str]]

    # SQL workflow
    sql_query: str
    sql_result: list[dict[str, Any]]

    # Analytics workflow
    analytics_result: str

    # Prediction workflow
    prediction_result: str

    # Output
    business_summary: str
    chart_path: str         # kept for backward compat (unused)
    chart_data: str         # JSON-encoded Plotly figure (plotly.io.to_json); "" when absent
    table_data: list        # top ≤10 rows as list[dict] for st.dataframe; [] when absent
    chart_insight: str      # one-sentence auto-generated insight; "" when absent

    # Metadata
    execution_time: float
    error: str
    conversation_id: str
    timestamp: str
