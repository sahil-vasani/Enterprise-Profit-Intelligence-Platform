"""
returns_engine.py — Return Cost Engine
=======================================

Generates return probability and associated cost variables.
Return rates are modulated by category, order value, promotions,
customer behaviour, and B2B flag — not random.

Generated columns
-----------------
return_probability        : P(this order will be returned) — 0 to 1
return_reason             : Most likely reason (size, quality, change_of_mind, etc.)
refund_amount             : INR refunded to customer
refurbishment_cost        : Cost to restore returned item to sellable condition
disposal_cost             : Cost to dispose of items that can't be resold

Why these columns don't exist in public datasets
-------------------------------------------------
Return rates and true refurbishment costs reveal product quality issues
and post-sale margin erosion — sensitive competitive information.
"""

import numpy as np
import pandas as pd

from config import CFG, get_return_rate


_REFURB_PCT = CFG["refurbishment_cost_pct"]
_DISPOSAL_PCT = CFG["disposal_cost_pct"]
_REFUND_PROC_PCT = CFG["refund_processing_cost_pct"]
_PROMO_RETURN_UPLIFT = 0.04   # promo orders return 4% more


_RETURN_REASONS = {
    "kurta":         ["size_mismatch", "quality_issue", "change_of_mind"],
    "Set":           ["size_mismatch", "color_mismatch", "quality_issue"],
    "Western Dress": ["size_mismatch", "style_not_as_expected", "change_of_mind"],
    "Top":           ["size_mismatch", "color_mismatch", "change_of_mind"],
    "Ethnic Dress":  ["size_mismatch", "quality_issue", "wrong_item"],
    "Blouse":        ["size_mismatch", "quality_issue", "change_of_mind"],
    "Bottom":        ["size_mismatch", "color_mismatch", "change_of_mind"],
    "Saree":         ["quality_issue", "color_mismatch", "wrong_item"],
    "Dupatta":       ["color_mismatch", "change_of_mind", "quality_issue"],
    "default":       ["change_of_mind", "quality_issue", "wrong_item"],
}


def _return_prob(row: pd.Series) -> float:
    """
    Compute return probability using business-rule modifiers.

    Base rate from config (category-specific).
    Adjustments:
    +4%  if promotional order (discount-chasing returns are higher)
    -5%  if B2B (institutional buyers return far less)
    +2%  if high-value order (>₹1000 — higher scrutiny on delivery)
    +3%  if repeat customer (higher expectations)
    -2%  if Amazon fulfilled (better packing, fewer errors)
    """
    base = get_return_rate(row.get("Category", "default"))

    promo = _PROMO_RETURN_UPLIFT if len(str(row.get("promotion-ids", "")).strip()) > 5 else 0
    b2b = -0.05 if str(row.get("B2B", "False")) == "True" else 0
    high_value = 0.02 if float(row.get("Amount", 0) or 0) > 1000 else 0
    repeat = 0.03 if int(row.get("repeat_customer_flag", 0)) == 1 else 0
    fulfil = -0.02 if str(row.get("Fulfilment", "")) == "Amazon" else 0

    p = base + promo + b2b + high_value + repeat + fulfil
    return round(max(0.01, min(p, 0.60)), 4)


def _return_reason(category: str, rng: np.random.Generator) -> str:
    reasons = _RETURN_REASONS.get(category, _RETURN_REASONS["default"])
    # Weight towards first reason (most likely)
    weights = [0.55, 0.30, 0.15][: len(reasons)]
    total = sum(weights)
    weights = [w / total for w in weights]
    return rng.choice(reasons, p=weights)


def run(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    df = df.copy()

    # ── Return Probability ────────────────────────────────────────────────────
    df["return_probability"] = df.apply(_return_prob, axis=1)

    # ── Return Reason ─────────────────────────────────────────────────────────
    df["return_reason"] = df["Category"].apply(
        lambda cat: _return_reason(cat, rng)
    )

    # Override for actually-returned orders in the dataset
    returned_mask = df["Status"].str.contains("Return", na=False)
    # Already returned — set probability to 1.0
    df.loc[returned_mask, "return_probability"] = 1.0

    # ── Refund Amount ─────────────────────────────────────────────────────────
    # For returned orders: full refund
    # For at-risk (prob > 0.15): expected loss = prob × amount
    # Cancelled orders: 0 refund needed (never shipped)
    cancelled_mask = df["Status"].str.startswith("Cancelled", na=False)
    df["refund_amount"] = 0.0
    df.loc[returned_mask, "refund_amount"] = df.loc[returned_mask, "Amount"].fillna(0)
    df.loc[~returned_mask & ~cancelled_mask, "refund_amount"] = (
        df.loc[~returned_mask & ~cancelled_mask, "return_probability"] *
        df.loc[~returned_mask & ~cancelled_mask, "Amount"].fillna(0)
    )
    df["refund_amount"] = df["refund_amount"].round(2)

    # ── Refurbishment Cost ────────────────────────────────────────────────────
    # Formula: refund_amount × refurbishment_pct
    # Only for actually returned items (not probabilistic)
    df["refurbishment_cost"] = 0.0
    df.loc[returned_mask, "refurbishment_cost"] = (
        df.loc[returned_mask, "refund_amount"] * _REFURB_PCT
    ).round(2)

    # ── Disposal Cost ─────────────────────────────────────────────────────────
    # Dead-stock items (if dead_stock_flag available) or very slow SKUs
    dead_mask = df.get("dead_stock_flag", pd.Series(0, index=df.index)).astype(bool)
    df["disposal_cost"] = 0.0
    if dead_mask.any():
        category_margin = df["Category"].apply(
            lambda c: 1 - CFG["category_margins"].get(c, CFG["category_margins"]["default"])
        )
        cogs = df["Amount"].fillna(0) * category_margin
        df.loc[dead_mask, "disposal_cost"] = (cogs[dead_mask] * _DISPOSAL_PCT).round(2)

    # ── Refund Processing Cost ────────────────────────────────────────────────
    df["refund_processing_cost"] = (df["refund_amount"] * _REFUND_PROC_PCT).round(2)

    return df
