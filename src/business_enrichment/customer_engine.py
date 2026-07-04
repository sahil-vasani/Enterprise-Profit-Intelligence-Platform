"""
customer_engine.py — Customer Simulation Engine
================================================

Generates customer-level intelligence columns by deriving behaviour
from existing transactional signals in the Amazon dataset.

Generated columns
-----------------
customer_id               : Deterministic hash of (ship-city + SKU style + order sequence)
customer_segment          : Champion / Loyal / Potential_Loyal / At_Risk / Lost
repeat_customer_flag      : 1 if customer_id appears > 1 time in dataset
loyalty_score             : 0–100 composite score
acquisition_channel       : Inferred from promotion-ids and fulfilment type
estimated_clv             : Estimated Customer Lifetime Value (INR)
estimated_cac             : Estimated Customer Acquisition Cost (INR)

Why these columns don't exist in public datasets
-------------------------------------------------
E-commerce platforms treat customer identity and CLV as proprietary.
Public order-level exports never include internal CRM IDs or CLV models.
"""

import hashlib
import numpy as np
import pandas as pd

from config import CFG


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_customer_id(row: pd.Series, counter: int) -> str:
    """
    Create a deterministic but opaque customer ID.

    Formula: SHA-1( city + state + style_prefix + order_index ) → first 10 hex chars
    The counter breaks ties for same city+style combos so repeat customers
    gradually cluster around the same style+geography, mimicking real buying patterns.
    """
    style_prefix = str(row.get("Style", "X"))[:3].upper()
    city = str(row.get("ship-city", "UNK")).upper()
    state = str(row.get("ship-state", "UNK")).upper()
    # B2B orders are more likely to be institutional — same customer ordering frequently
    b2b_salt = "B2B" if str(row.get("B2B", "False")) == "True" else "B2C"
    raw = f"{city}|{state}|{style_prefix}|{b2b_salt}|{counter % 5}"
    return "C" + hashlib.sha1(raw.encode()).hexdigest()[:9].upper()


def _infer_acquisition_channel(row: pd.Series) -> str:
    """
    Infer how the customer found the product.

    Logic:
    - PLCC promotion → Credit_Card_Offer
    - Non-empty promotions (non-PLCC) → Promotional_Campaign
    - Amazon fulfilment, no promo → Organic_Search
    - Merchant fulfilment → Direct / Social
    - B2B → Enterprise_Sales
    """
    is_b2b = str(row.get("B2B", "False")) == "True"
    if is_b2b:
        return "Enterprise_Sales"
    promos = str(row.get("promotion-ids", ""))
    if "PLCC" in promos:
        return "Credit_Card_Offer"
    if len(promos.strip()) > 5:
        return "Promotional_Campaign"
    if str(row.get("Fulfilment", "")) == "Amazon":
        return "Organic_Search"
    return "Social_or_Direct"


# ─────────────────────────────────────────────────────────────────────────────
#  Main Engine
# ─────────────────────────────────────────────────────────────────────────────

def run(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extend df with customer intelligence columns.
    Returns df with new columns appended (original columns unchanged).
    """
    cfg_seg = CFG["segment_thresholds"]
    cfg_clv = CFG["clv_multiplier"]
    cfg_cac = CFG["default_cac"]

    # ── Step 1: Assign customer IDs ───────────────────────────────────────────
    # Counter resets every N rows to create ~realistic repeat-buy clusters
    rng = np.random.default_rng(seed=42)

    # For B2B orders: same customer buys multiple times — use a tighter counter
    counters = []
    b2b_counter_map: dict[str, int] = {}
    b2c_counter: int = 0

    for _, row in df.iterrows():
        is_b2b = str(row.get("B2B", "False")) == "True"
        if is_b2b:
            key = str(row.get("ship-city", ""))[:4] + str(row.get("Style", ""))[:3]
            b2b_counter_map[key] = b2b_counter_map.get(key, 0)
            counters.append(b2b_counter_map[key])
            # B2B customers repeat more — increment counter slowly
            b2b_counter_map[key] += rng.integers(0, 2)
        else:
            counters.append(b2c_counter)
            # B2C: moderate repeat probability (~20%)
            b2c_counter += rng.integers(1, 6)

    df = df.copy()
    df["customer_id"] = [
        _make_customer_id(row, cnt)
        for (_, row), cnt in zip(df.iterrows(), counters)
    ]

    # ── Step 2: Order frequency per customer ─────────────────────────────────
    freq = df["customer_id"].value_counts().rename("_order_freq")
    df = df.join(freq, on="customer_id")

    df["repeat_customer_flag"] = (df["_order_freq"] > 1).astype(int)

    # ── Step 3: Customer segment ──────────────────────────────────────────────
    def _segment(freq: int) -> str:
        if freq >= cfg_seg["champion_orders"]:
            return "Champion"
        if freq >= cfg_seg["loyal_orders"]:
            return "Loyal"
        if freq >= cfg_seg["potential_loyal_orders"]:
            return "Potential_Loyal"
        return "At_Risk"

    df["customer_segment"] = df["_order_freq"].apply(_segment)

    # ── Step 4: Loyalty score ─────────────────────────────────────────────────
    # Formula: 40*repeat_flag + 30*(freq_norm) + 20*(avg_order_value_norm) + 10*(promo_flag)
    max_freq = df["_order_freq"].max()
    amount_filled = df["Amount"].fillna(0)
    max_amount = amount_filled.max() if amount_filled.max() > 0 else 1

    has_promo = df["promotion-ids"].apply(
        lambda x: 1 if len(str(x).strip()) > 5 else 0
    )

    df["loyalty_score"] = (
        40 * df["repeat_customer_flag"]
        + 30 * (df["_order_freq"] / max_freq)
        + 20 * (amount_filled / max_amount)
        + 10 * has_promo
    ).clip(0, 100).round(1)

    # ── Step 5: Acquisition channel ───────────────────────────────────────────
    df["acquisition_channel"] = df.apply(_infer_acquisition_channel, axis=1)

    # ── Step 6: Estimated CLV ─────────────────────────────────────────────────
    # Formula: avg_order_value × order_frequency × clv_multiplier(segment)
    # CLV represents predicted total revenue from this customer over their lifetime.
    avg_ov = df.groupby("customer_id")["Amount"].mean().fillna(0).rename("_avg_ov")
    df = df.join(avg_ov, on="customer_id")

    df["estimated_clv"] = (
        df["_avg_ov"]
        * df["_order_freq"]
        * df["customer_segment"].map(cfg_clv)
    ).round(2)

    # ── Step 7: Estimated CAC ─────────────────────────────────────────────────
    # CAC = base_cac × (1 + promo_uplift) × (1 if repeat else 1.3 for new customers)
    base_cac = df["B2B"].apply(lambda x: cfg_cac["B2B"] if str(x) == "True" else cfg_cac["B2C"])
    promo_uplift = has_promo * 0.25   # promotions cost 25% more to acquire
    new_customer_premium = (1 - df["repeat_customer_flag"]) * 0.30

    df["estimated_cac"] = (
        base_cac * (1 + promo_uplift + new_customer_premium)
    ).round(2)

    # ── Cleanup internal columns ──────────────────────────────────────────────
    df.drop(columns=["_order_freq", "_avg_ov"], inplace=True)

    return df
