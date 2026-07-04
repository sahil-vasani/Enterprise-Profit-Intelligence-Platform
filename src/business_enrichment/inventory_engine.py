"""
inventory_engine.py — Inventory Simulation Engine
==================================================

Derives inventory variables from SKU-level sales history.
All values are calculated from actual demand signals — not random.

Generated columns
-----------------
inventory_available       : Estimated units on hand at time of order
inventory_age_days        : Days stock has been sitting (older = higher holding cost)
reorder_point             : Units at which a reorder is triggered
safety_stock              : Buffer stock in units
reorder_quantity           : Economic order quantity approximation
inventory_turnover        : Times inventory turned over in the dataset period
dead_stock_flag           : 1 if SKU has low velocity AND high age
stockout_probability      : Probability of stockout in next 7 days (0–1)

Why these columns don't exist in public datasets
-------------------------------------------------
Inventory positions are real-time operational secrets.  Exposing them
would reveal supplier relationships, warehouse capacity, and reorder
strategies — all of which are core competitive IP.
"""

import numpy as np
import pandas as pd

from config import CFG


def run(df: pd.DataFrame) -> pd.DataFrame:
    cfg = CFG
    safety_days = cfg["safety_stock_days"]
    lead_days = cfg["lead_time_days"]
    reorder_days = cfg["reorder_days_supply"]
    dead_stock_threshold = cfg["dead_stock_age_threshold"]

    df = df.copy()

    # ── Step 1: SKU-level demand statistics ───────────────────────────────────
    # Use only non-cancelled, non-returned orders as "real" demand
    valid_mask = ~df["Status"].str.startswith("Cancelled") & \
                 ~df["Status"].str.contains("Return", na=False)

    sku_stats = (
        df[valid_mask]
        .groupby("SKU")["Qty"]
        .agg(
            sku_total_sold="sum",
            sku_order_count="count",
            sku_avg_qty="mean",
            sku_std_qty="std",
        )
        .fillna(0)
    )

    # Dataset date range in days
    df["_date_parsed"] = pd.to_datetime(df["Date"], format="%m-%d-%y", errors="coerce")
    dataset_days = (df["_date_parsed"].max() - df["_date_parsed"].min()).days
    dataset_days = max(dataset_days, 1)

    # Daily demand per SKU
    sku_stats["daily_demand"] = sku_stats["sku_total_sold"] / dataset_days
    sku_stats["demand_std_daily"] = sku_stats["sku_std_qty"] / np.sqrt(dataset_days + 1)

    df = df.join(sku_stats, on="SKU")

    # ── Step 2: Reorder Point ─────────────────────────────────────────────────
    # Formula: ROP = (daily_demand × lead_time) + safety_stock
    # Safety stock = Z × σ_daily × √lead_time   (Z=1.65 for 95% service level)
    Z = 1.65
    df["safety_stock"] = (
        Z * df["demand_std_daily"].fillna(0) * np.sqrt(lead_days)
    ).clip(lower=1).round(0).astype(int)

    df["reorder_point"] = (
        df["daily_demand"].fillna(0) * lead_days + df["safety_stock"]
    ).round(0).astype(int)

    # ── Step 3: Reorder Quantity ──────────────────────────────────────────────
    # EOQ approximation: reorder enough to cover `reorder_days_supply` of demand
    df["reorder_quantity"] = (
        df["daily_demand"].fillna(0) * reorder_days
    ).clip(lower=1).round(0).astype(int)

    # ── Step 4: Inventory Available ───────────────────────────────────────────
    # Simulated stock on hand at time of order.
    # Logic: Start with reorder_quantity, subtract cumulative demand per SKU per date.
    df_sorted = df.sort_values(["SKU", "_date_parsed"])
    cumulative_qty = df_sorted.groupby("SKU")["Qty"].cumsum().fillna(0)

    starting_stock = df["reorder_quantity"] * 2   # assume 2-cycle stock at start
    df["inventory_available"] = (
        starting_stock - cumulative_qty.values + df["reorder_quantity"].values
    ).clip(lower=0).round(0).astype(int)

    # ── Step 5: Inventory Age ─────────────────────────────────────────────────
    # Proxy: older SKUs with low velocity have older inventory
    # Formula: age = max(days since first sale, 1) × (1 / velocity_factor)
    sku_first_sale = (
        df[valid_mask]
        .groupby("SKU")["_date_parsed"]
        .min()
        .rename("sku_first_sale")
    )
    df = df.join(sku_first_sale, on="SKU")

    days_since_first = (df["_date_parsed"] - df["sku_first_sale"]).dt.days.fillna(0).clip(lower=1)
    # Velocity factor: high daily demand → faster turnover → newer stock
    vel_factor = (df["daily_demand"].fillna(0) + 0.01)
    df["inventory_age_days"] = (
        days_since_first / (vel_factor * 5)
    ).clip(lower=1, upper=365).round(0).astype(int)

    # ── Step 6: Inventory Turnover ────────────────────────────────────────────
    # Formula: Total units sold / avg inventory level (annualised to dataset period)
    avg_inventory = df["reorder_quantity"] / 2   # avg of max and 0
    annual_factor = 365 / dataset_days
    df["inventory_turnover"] = (
        (df["sku_total_sold"] / avg_inventory.clip(lower=1)) * annual_factor
    ).round(2)

    # ── Step 7: Dead Stock Flag ───────────────────────────────────────────────
    # Flag: age > threshold AND daily_demand < 0.5 units/day
    df["dead_stock_flag"] = (
        (df["inventory_age_days"] > dead_stock_threshold) &
        (df["daily_demand"].fillna(0) < 0.5)
    ).astype(int)

    # ── Step 8: Stockout Probability ─────────────────────────────────────────
    # P(stockout in 7 days) = P(demand_7days > inventory_available)
    # Approximated via normal CDF: P(X > inv) where X ~ N(7×daily, 7×σ²)
    from scipy.stats import norm
    mu_7d = df["daily_demand"].fillna(0) * 7
    sigma_7d = (df["demand_std_daily"].fillna(0) * np.sqrt(7)).clip(lower=0.01)
    inv = df["inventory_available"].clip(lower=0)

    df["stockout_probability"] = norm.sf(inv, loc=mu_7d, scale=sigma_7d).round(4).clip(0, 1)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    drop_cols = [c for c in [
        "_date_parsed", "sku_total_sold", "sku_order_count",
        "sku_avg_qty", "sku_std_qty", "daily_demand",
        "demand_std_daily", "sku_first_sale"
    ] if c in df.columns]
    df.drop(columns=drop_cols, inplace=True)

    return df
