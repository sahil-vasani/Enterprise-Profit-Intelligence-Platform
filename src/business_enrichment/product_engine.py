"""
product_engine.py — Product Intelligence Engine
================================================

Classifies every SKU using sales history into standard supply-chain
and product-management frameworks.

Generated columns
-----------------
lifecycle_stage           : Introduction / Growth / Maturity / Decline
velocity_class            : Fast / Medium / Slow (units sold per day)
abc_class                 : A / B / C (revenue contribution Pareto)
xyz_class                 : X / Y / Z (demand variability)
contribution_margin       : Revenue − COGS − Variable Costs (INR)
product_profitability_score: 0–100 composite score
dead_stock_score          : 0–100 risk score for becoming dead inventory

Why these columns don't exist in public datasets
-------------------------------------------------
SKU classification is a core merchandising and buying-team asset.
ABC/XYZ matrices directly inform procurement strategy and are never shared.
"""

import numpy as np
import pandas as pd

from config import CFG, get_category_margin, get_platform_commission, get_packaging_cost


_LIFECYCLE = CFG["lifecycle_thresholds"]
_ABC = CFG["abc_thresholds"]
_XYZ = CFG["xyz_thresholds"]


# ── ABC Classification ────────────────────────────────────────────────────────

def _abc_classify(df_valid: pd.DataFrame) -> pd.Series:
    """
    Assign A / B / C based on cumulative revenue contribution.
    A = top SKUs making up 70% of revenue
    B = next 20%
    C = remaining 10%
    """
    sku_rev = df_valid.groupby("SKU")["Amount"].sum().sort_values(ascending=False)
    cumulative = sku_rev.cumsum() / sku_rev.sum()
    labels = []
    for val in cumulative:
        if val <= _ABC["A"]:
            labels.append("A")
        elif val <= _ABC["B"]:
            labels.append("B")
        else:
            labels.append("C")
    return pd.Series(labels, index=cumulative.index)


# ── XYZ Classification ────────────────────────────────────────────────────────

def _xyz_classify(df_valid: pd.DataFrame) -> pd.Series:
    """
    XYZ based on Coefficient of Variation (CV) of weekly demand per SKU.
    X: CV ≤ 0.30  (predictable)
    Y: CV ≤ 0.60  (moderate variability)
    Z: CV > 0.60  (unpredictable)
    """
    df_valid = df_valid.copy()
    df_valid["_date_parsed"] = pd.to_datetime(df_valid["Date"], format="%m-%d-%y", errors="coerce")
    df_valid["_week"] = df_valid["_date_parsed"].dt.isocalendar().week

    weekly = (
        df_valid.groupby(["SKU", "_week"])["Qty"].sum().reset_index()
    )
    cv = weekly.groupby("SKU")["Qty"].apply(
        lambda x: x.std() / x.mean() if x.mean() > 0 else 0
    )
    xyz = cv.copy().astype(str)
    xyz[cv <= _XYZ["X"]] = "X"
    xyz[(cv > _XYZ["X"]) & (cv <= _XYZ["Y"])] = "Y"
    xyz[cv > _XYZ["Y"]] = "Z"
    return xyz


def run(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # ── Date parsing for lifecycle ────────────────────────────────────────────
    df["_date_parsed"] = pd.to_datetime(df["Date"], format="%m-%d-%y", errors="coerce")

    valid_mask = (
        ~df["Status"].str.startswith("Cancelled", na=False) &
        ~df["Status"].str.contains("Return", na=False)
    )
    df_valid = df[valid_mask]

    sku_first_sale = df_valid.groupby("SKU")["_date_parsed"].min().rename("_first_sale")
    dataset_end = df["_date_parsed"].max()
    df = df.join(sku_first_sale, on="SKU")
    df["_sku_age_days"] = (dataset_end - df["_first_sale"]).dt.days.fillna(0).clip(lower=0)

    # ── Lifecycle Stage ────────────────────────────────────────────────────────
    def _lifecycle(age: float) -> str:
        if age <= _LIFECYCLE["introduction_days"]:
            return "Introduction"
        if age <= _LIFECYCLE["growth_days"]:
            return "Growth"
        if age <= _LIFECYCLE["maturity_days"]:
            return "Maturity"
        return "Decline"

    df["lifecycle_stage"] = df["_sku_age_days"].apply(_lifecycle)

    # ── Velocity Class ────────────────────────────────────────────────────────
    # Daily demand: units sold / days in dataset
    dataset_days = max((df["_date_parsed"].max() - df["_date_parsed"].min()).days, 1)
    sku_daily = (
        df_valid.groupby("SKU")["Qty"].sum() / dataset_days
    ).rename("_daily_vel")
    df = df.join(sku_daily, on="SKU")
    df["_daily_vel"] = df["_daily_vel"].fillna(0)

    def _velocity(d: float) -> str:
        if d >= 3.0:
            return "Fast"
        if d >= 0.5:
            return "Medium"
        return "Slow"

    df["velocity_class"] = df["_daily_vel"].apply(_velocity)

    # ── ABC Classification ────────────────────────────────────────────────────
    abc_map = _abc_classify(df_valid)
    df = df.join(abc_map.rename("abc_class"), on="SKU")
    df["abc_class"] = df["abc_class"].fillna("C")

    # ── XYZ Classification ────────────────────────────────────────────────────
    xyz_map = _xyz_classify(df_valid)
    df = df.join(xyz_map.rename("xyz_class"), on="SKU")
    df["xyz_class"] = df["xyz_class"].fillna("Z")

    # ── Contribution Margin ───────────────────────────────────────────────────
    # Formula: Revenue − COGS − Packaging − Shipping (variable costs only)
    # Uses columns already added by finance/logistics engines if available,
    # otherwise estimates from config.
    revenue = df["Amount"].fillna(0)
    margin_pct = df["Category"].apply(get_category_margin)
    cogs = revenue * (1 - margin_pct)
    packaging = df["Category"].apply(get_packaging_cost) * df["Qty"].fillna(1)
    shipping = df.get("shipping_cost", pd.Series(0, index=df.index)).fillna(0)

    df["contribution_margin"] = (revenue - cogs - packaging - shipping).round(2)

    # ── Product Profitability Score ───────────────────────────────────────────
    # Composite: 40% contribution margin (normalised) + 30% ABC + 20% velocity + 10% lifecycle
    cm_norm = df["contribution_margin"].clip(lower=0)
    cm_score = (cm_norm / max(cm_norm.max(), 1) * 40).fillna(0)

    abc_score = df["abc_class"].map({"A": 30, "B": 20, "C": 10}).fillna(10)
    vel_score = df["velocity_class"].map({"Fast": 20, "Medium": 13, "Slow": 5}).fillna(5)
    lc_score = df["lifecycle_stage"].map(
        {"Growth": 10, "Maturity": 8, "Introduction": 5, "Decline": 2}
    ).fillna(5)

    df["product_profitability_score"] = (
        cm_score + abc_score + vel_score + lc_score
    ).clip(0, 100).round(1)

    # ── Dead Stock Score ──────────────────────────────────────────────────────
    # Higher = more at risk of becoming dead stock
    # Inputs: slow velocity, old inventory, C-class, Decline stage
    vel_risk = df["velocity_class"].map({"Slow": 50, "Medium": 20, "Fast": 0}).fillna(50)
    abc_risk = df["abc_class"].map({"C": 30, "B": 15, "A": 0}).fillna(30)
    lc_risk = df["lifecycle_stage"].map(
        {"Decline": 20, "Maturity": 5, "Growth": 0, "Introduction": 0}
    ).fillna(0)

    df["dead_stock_score"] = (vel_risk + abc_risk + lc_risk).clip(0, 100).round(1)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    df.drop(columns=[c for c in ["_date_parsed", "_sku_age_days", "_first_sale", "_daily_vel"]
                     if c in df.columns], inplace=True)

    return df
