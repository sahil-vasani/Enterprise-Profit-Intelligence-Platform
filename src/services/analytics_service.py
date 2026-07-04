"""
analytics_service.py - Abstraction layer for analytics modules.
"""
from analytics import (
    profit_analysis,
    customer_analysis,
    inventory_analysis,
    marketing_analysis,
    returns_analysis,
    statistical_analysis,
    product_analysis
)

MODULE_REGISTRY = {
    "Profit Analysis": profit_analysis.run,
    "Customer Analysis": customer_analysis.run,
    "Inventory Analysis": inventory_analysis.run,
    "Marketing Analysis": marketing_analysis.run,
    "Returns Analysis": returns_analysis.run,
    "Statistical Analysis": statistical_analysis.run,
    "Product Analysis": product_analysis.run
}

def get_analytics_modules() -> list[dict]:
    """Returns the list of available analytics modules with metadata."""
    return [
        {"title": "Profit Analysis", "icon": "💰", "desc": "Analyze margins, profitability drivers and cost centers."},
        {"title": "Customer Analysis", "icon": "👥", "desc": "Analyze retention, lifetime value, and segmentation."},
        {"title": "Inventory Analysis", "icon": "📦", "desc": "Identify slow moving stock, turnover rates and stockouts."},
        {"title": "Marketing Analysis", "icon": "🎯", "desc": "Measure campaign ROI, acquisition costs, and conversion."},
        {"title": "Returns Analysis", "icon": "🔄", "desc": "Analyze return rates by product category and reason."},
        {"title": "Product Analysis", "icon": "🏷️", "desc": "Analyze product performance, cross-selling and categories."},
        {"title": "Statistical Analysis", "icon": "📈", "desc": "Discover trends, correlations, and anomalies."}
    ]
