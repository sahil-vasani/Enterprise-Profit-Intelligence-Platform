"""
marketing_engine.py — Marketing Attribution Engine
====================================================

Infers campaign attribution from existing promotion-ids column.
When no promotion exists, assigns organic baseline.

Generated columns
-----------------
campaign_name             : Internal campaign label
campaign_type             : PLCC_Financing / Flash_Sale / Seasonal / Loyalty / Organic
campaign_cost             : Estimated marketing spend attributed to this order (INR)
campaign_roi              : Revenue generated per INR of campaign spend
attributed_revenue        : Portion of revenue directly attributed to campaign
discount_cost             : Lost revenue from promotion discount
marketing_attribution_cost: Per-order share of total campaign cost

Why these columns don't exist in public datasets
-------------------------------------------------
Campaign-level spend and ROI are core marketing team confidential metrics.
Amazon's public exports only show promotion IDs, not the underlying economics.
"""

import numpy as np
import pandas as pd

from config import CFG


_ROI_MULT = CFG["campaign_roi_multiplier"]
_DEFAULT_CAC = CFG["default_cac"]
_PROMO_MARGIN_IMPACT = CFG["promo_margin_impact"]


def _classify_campaign(promo_str: str) -> tuple[str, str]:
    """
    Map promotion-ids string to (campaign_name, campaign_type).
    """
    p = str(promo_str).strip()
    if len(p) < 5:
        return ("Organic", "Organic")
    if "PLCC" in p:
        return ("Amazon_PLCC_Financing", "PLCC_Financing")
    if "FLASH" in p.upper():
        return ("Flash_Sale_Campaign", "Flash_Sale")
    if "LOYAL" in p.upper():
        return ("Loyalty_Program", "Loyalty")
    # Generic seasonal promo
    return ("Seasonal_Promotion", "Seasonal")


def run(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Campaign classification ────────────────────────────────────────────────
    campaigns = df["promotion-ids"].apply(_classify_campaign)
    df["campaign_name"] = campaigns.apply(lambda x: x[0])
    df["campaign_type"] = campaigns.apply(lambda x: x[1])

    # ── Discount cost ─────────────────────────────────────────────────────────
    # Promo orders are estimated to have been discounted by promo_margin_impact
    # We model the discount as the revenue forgone vs. full price.
    # Formula: discount_cost = Amount × promo_margin_impact  (if promo exists)
    has_promo = df["campaign_type"] != "Organic"
    df["discount_cost"] = 0.0
    df.loc[has_promo, "discount_cost"] = (
        df.loc[has_promo, "Amount"].fillna(0) * _PROMO_MARGIN_IMPACT
    ).round(2)

    # ── Attributed revenue ────────────────────────────────────────────────────
    # Revenue that would NOT have happened without the campaign
    # For organic: 0 (no campaign needed)
    # For promo: portion of revenue incremental to baseline demand
    # Assumption: ~40% of promo revenue is incremental (rest would have sold anyway)
    df["attributed_revenue"] = 0.0
    df.loc[has_promo, "attributed_revenue"] = (
        df.loc[has_promo, "Amount"].fillna(0) * 0.40
    ).round(2)

    # ── Campaign cost per order ────────────────────────────────────────────────
    # Estimated as: CAC × (1 if organic else campaign_type_multiplier factor)
    is_b2b = df["B2B"].astype(str) == "True"
    base_cac = is_b2b.map({True: _DEFAULT_CAC["B2B"], False: _DEFAULT_CAC["B2C"]})

    # PLCC campaigns are partially funded by the bank — lower per-order cost
    type_factor = df["campaign_type"].map({
        "PLCC_Financing": 0.40,
        "Flash_Sale":     0.80,
        "Seasonal":       0.65,
        "Loyalty":        0.50,
        "Organic":        0.00,
    }).fillna(0.65)

    df["marketing_attribution_cost"] = (base_cac * type_factor).round(2)
    # campaign_cost = attribution + discount
    df["campaign_cost"] = (df["marketing_attribution_cost"] + df["discount_cost"]).round(2)

    # ── Campaign ROI ──────────────────────────────────────────────────────────
    # Formula: attributed_revenue / campaign_cost  (avoid div/0)
    safe_cost = df["campaign_cost"].replace(0, np.nan)
    df["campaign_roi"] = (df["attributed_revenue"] / safe_cost).fillna(
        _ROI_MULT["None"]
    ).round(3)

    return df
