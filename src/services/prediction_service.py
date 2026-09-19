"""
prediction_service.py — Abstraction layer for ML Predictions (Streamlit UI).

Calls dynamic_trainer directly for model metadata and run_backend_query
for the LLM-formatted business narrative.
"""
import sys
from pathlib import Path

# Add src/ml to path so dynamic_trainer can be imported
_ML_DIR = Path(__file__).resolve().parents[1] / "ml"
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

import dynamic_trainer  # noqa: E402
from services.copilot_service import run_backend_query

# Map UI-facing target labels to dataset column names
_TARGET_COL_MAP = {
    "Net Profit":    "net_profit",
    "Revenue":       "Amount",
    "Gross Profit":  "gross_profit",
    "Shipping Cost": "shipping_cost",
    "Refund Amount": "refund_amount",
    "COGS":          "cogs",
}

# Map UI horizon labels to days
_HORIZON_DAYS_MAP = {
    "next week":    7,
    "next month":   30,
    "next quarter": 90,
    "next year":    365,
}


def run_prediction(target: str, horizon: str, confidence: int) -> dict:
    """
    Execute a prediction via dynamic_trainer and enrich with LLM narrative.

    Parameters
    ----------
    target     : Human-readable target label (e.g., "Net Profit", "Revenue")
    horizon    : Human-readable horizon label (e.g., "next month", "next week")
    confidence : Confidence % integer (e.g., 90, 95)

    Returns
    -------
    dict with keys: business_summary, prediction_result, model_name,
                    confidence, feature_importance
    """
    target_col   = _TARGET_COL_MAP.get(target, "net_profit")
    horizon_days = _HORIZON_DAYS_MAP.get(horizon.lower(), 30)

    # Build a natural-language question that routes through the full copilot pipeline
    question = (
        f"What will be the {target.lower()} in the {horizon}? "
        f"Use {confidence}% confidence."
    )
    res = run_backend_query(question)

    # Get model metadata directly from dynamic_trainer (load or train)
    try:
        model, feature_cols, medians, was_cached = dynamic_trainer._get_or_train(target_col)
        model_name   = type(model).__name__
        top_features = feature_cols[:3] if feature_cols else ["Category", "Qty", "Amount"]
    except Exception:
        model_name   = "RandomForestRegressor"
        top_features = ["Category", "Qty", "Amount"]

    res["model_name"]         = model_name
    res["confidence"]         = f"{confidence}%"
    res["feature_importance"] = ", ".join(
        [f.replace("_", " ").title() for f in top_features]
    )

    return res

