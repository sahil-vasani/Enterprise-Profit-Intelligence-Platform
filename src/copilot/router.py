"""
router.py — Intent classification for the AI Business Copilot.
Uses keyword matching as a fast, offline fallback. LLM-based routing will be added in Prompt 2.
"""

from logger import get_logger

log = get_logger("router")

# Keyword groups for each intent
_SQL_KEYWORDS = [
    "revenue", "sales", "orders", "top", "bottom", "total", "count", "sum",
    "average", "warehouse", "state", "city", "category", "product", "sku",
    "customer", "courier", "channel", "show me", "list", "how many",
    "which", "where", "highest", "lowest", "most", "least", "by region",
    "by category", "by state", "by month", "distribution",
]

_ANALYTICS_KEYWORDS = [
    "why", "analyse", "analyze", "analysis", "compare", "comparison",
    "trend", "insight", "driver", "cause", "impact", "segmentation",
    "decreasing", "increasing", "declining", "growing", "performance",
    "breakdown", "correlation", "return rate", "churn",
]

_PREDICTION_KEYWORDS = [
    "predict", "forecast", "estimate", "next month", "next quarter",
    "future", "projection", "expected", "will be", "what if",
]

_REPORT_KEYWORDS = [
    "report", "summary", "executive", "ceo", "briefing", "overview",
    "dashboard", "generate report", "monthly report", "business review",
]


def classify_intent(question: str) -> str:
    """Classify a user question into one of: sql, analytics, prediction, report, general."""
    q = question.lower().strip()

    # Check each intent group in priority order
    if any(kw in q for kw in _PREDICTION_KEYWORDS):
        intent = "prediction"
    elif any(kw in q for kw in _REPORT_KEYWORDS):
        intent = "report"
    elif any(kw in q for kw in _ANALYTICS_KEYWORDS):
        intent = "analytics"
    elif any(kw in q for kw in _SQL_KEYWORDS):
        intent = "sql"
    else:
        intent = "general"

    log.info("Intent classified: '%s' → %s", question[:60], intent)
    return intent
