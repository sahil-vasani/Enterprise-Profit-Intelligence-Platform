"""
prediction_agent.py — Dynamic multi-target prediction agent.

Parses the user's question to extract:
  - target      : which metric to predict  (net_profit, Amount, etc.)
  - horizon_days: how many days ahead       (7, 20, 30, 90, ...)
  - confidence  : CI level                 (0.80, 0.90, 0.95, 0.99)

Then calls dynamic_trainer.predict() which:
  - loads a cached model   (fast ⚡) if models/{target}_model.pkl exists, OR
  - trains a new model     (auto 🏋️) with leakage-free feature selection.

Returns a structured LLM response with predicted value + CI bounds.
"""

import re
import sys
from pathlib import Path

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm import get_llm
from state import CopilotState
from logger import get_logger

# Add src/ml/ to sys.path so dynamic_trainer can be imported
_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

import dynamic_trainer  # noqa: E402

log = get_logger("prediction_agent")

# ── Target keyword map ────────────────────────────────────────────────────────
# Order matters — more specific phrases first.
_TARGET_MAP: list[tuple[list[str], str]] = [
    (["net profit", "net_profit", "overall profit"],     "net_profit"),
    (["gross profit", "gross_profit"],                   "gross_profit"),
    (["revenue", "sales", "turnover", "amount earned"],  "Amount"),
    (["shipping cost", "shipping"],                      "shipping_cost"),
    (["refund", "return amount", "refund amount"],       "refund_amount"),
    (["cogs", "cost of goods", "cost of product"],       "cogs"),
    (["profit"],                                         "net_profit"),   # generic fallback
]

# ── Horizon keyword map ────────────────────────────────────────────────────────
_HORIZON_MAP: list[tuple[list[str], int]] = [
    (["next week", "this week", "7 days", "one week"],                 7),
    (["next month", "this month", "30 days", "one month"],            30),
    (["next quarter", "90 days", "three months", "this quarter"],     90),
    (["next year", "365 days", "one year", "this year"],             365),
]

# ── Human-readable target labels ──────────────────────────────────────────────
_TARGET_LABELS: dict[str, str] = {
    "net_profit":    "Net Profit",
    "Amount":        "Revenue (Sales Amount)",
    "gross_profit":  "Gross Profit",
    "shipping_cost": "Shipping Cost",
    "refund_amount": "Refund Amount",
    "cogs":          "Cost of Goods Sold (COGS)",
}

# ── LLM prompt ────────────────────────────────────────────────────────────────
_PREDICTION_PROMPT = """\
You are an AI Business Copilot for an Amazon India e-commerce seller.
The user asked: "{question}"

Our ML model generated the following forecast:
- Metric Predicted : {target_label}
- Forecast Horizon : Next {horizon_days} days
- Predicted Value  : {prediction_value}
- {confidence_pct}% Confidence Interval : {lower_bound}  to  {upper_bound}
- Model Status     : {model_status}
- Avg Daily Orders : {daily_orders} orders/day
- Features Used    : {features_used} business drivers

Your response must include:
1. A clear, one-sentence statement of the predicted value and CI range.
2. A 1-2 sentence business interpretation of what this means.
3. One specific, actionable recommendation based on this forecast.

Keep it concise, professional, and in plain text. Do not show code or formulas.
Response:"""


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_target(question: str) -> str:
    """Extract prediction target column from user question. Defaults to 'net_profit'."""
    q = question.lower()
    for keywords, col in _TARGET_MAP:
        if any(kw in q for kw in keywords):
            return col
    return "net_profit"


def _parse_horizon(question: str) -> int:
    """Extract forecast horizon in days from user question. Defaults to 30."""
    q = question.lower()

    # Fixed keyword map first (most specific)
    for keywords, days in _HORIZON_MAP:
        if any(kw in q for kw in keywords):
            return days

    # Numeric: "after 20 days", "next 20 days", "in 15 days", "for 45 days"
    match = re.search(r"(?:after|next|in|for)\s+(\d+)\s*(?:days?|d\b)", q)
    if match:
        return int(match.group(1))

    # Bare number before "days"
    match = re.search(r"(\d+)\s*days?", q)
    if match:
        return int(match.group(1))

    return 30  # default


def _parse_confidence(question: str) -> float:
    """Extract confidence level from question. Defaults to 0.90."""
    q = question.lower()
    match = re.search(r"(\d+)\s*%?\s*confidence", q)
    if match:
        val = int(match.group(1))
        return val / 100 if val > 1 else float(val)
    if "high confidence" in q or "very confident" in q:
        return 0.99
    if "low confidence" in q:
        return 0.80
    return 0.90


def _fmt_inr(value: float) -> str:
    """Format a number as Indian Rupees with commas."""
    return f"\u20b9{value:,.0f}"


# ── Agent entry point ─────────────────────────────────────────────────────────

def run_prediction_agent(state: CopilotState) -> CopilotState:
    """
    Main agent pipeline:
      parse question → dynamic_trainer.predict() → LLM explanation → state.
    """
    log.info("Prediction Agent: started")
    question = state.get("question", "")

    if not question:
        state["error"] = "No question provided."
        state["business_summary"] = "I did not receive a question to answer."
        return state

    try:
        # ── 1. Parse prediction intent ────────────────────────────────────────
        target       = _parse_target(question)
        horizon_days = _parse_horizon(question)
        confidence   = _parse_confidence(question)

        log.info(
            "Parsed → target='%s'  horizon=%dd  confidence=%.0f%%",
            target, horizon_days, confidence * 100,
        )

        # ── 2. Predict (cache HIT or auto-train) ──────────────────────────────
        result = dynamic_trainer.predict(
            target=target,
            horizon_days=horizon_days,
            confidence=confidence,
        )

        # ── 3. Format values ──────────────────────────────────────────────────
        prediction_str   = _fmt_inr(result["prediction"])
        lower_str        = _fmt_inr(result["lower_bound"])
        upper_str        = _fmt_inr(result["upper_bound"])
        confidence_pct   = int(confidence * 100)
        target_label     = _TARGET_LABELS.get(target, target.replace("_", " ").title())
        model_status     = (
            "Loaded from cache \u26a1 (instant)"
            if result["model_was_cached"]
            else "Freshly trained \U0001f3cb\ufe0f (auto-trained for this metric)"
        )

        # ── 4. LLM narrative explanation ──────────────────────────────────────
        llm = get_llm()
        prompt = PromptTemplate(
            input_variables=[
                "question", "target_label", "horizon_days",
                "prediction_value", "confidence_pct",
                "lower_bound", "upper_bound",
                "model_status", "features_used", "daily_orders",
            ],
            template=_PREDICTION_PROMPT,
        )
        chain = prompt | llm | StrOutputParser()

        summary = chain.invoke({
            "question":         question,
            "target_label":     target_label,
            "horizon_days":     horizon_days,
            "prediction_value": prediction_str,
            "confidence_pct":   confidence_pct,
            "lower_bound":      lower_str,
            "upper_bound":      upper_str,
            "model_status":     model_status,
            "features_used":    result["features_used"],
            "daily_orders":     result["daily_orders"],
        })

        state["business_summary"]  = summary.strip()
        state["prediction_result"] = prediction_str

        log.info("Prediction Agent: done — %s", prediction_str)

    except Exception as exc:
        log.error("Prediction Agent error: %s", exc, exc_info=True)
        state["error"]            = str(exc)
        state["business_summary"] = (
            f"An error occurred while generating the prediction: {exc}"
        )

    return state

