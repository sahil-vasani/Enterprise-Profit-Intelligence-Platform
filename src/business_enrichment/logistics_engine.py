"""
logistics_engine.py — Logistics Simulation Engine
==================================================

Generates shipping and fulfilment cost variables from state,
fulfilment type, product weight, and quantity.

Generated columns
-----------------
warehouse_zone            : Tier-1 / Tier-2 / Tier-3 (metro / large city / remote)
estimated_shipping_distance: Approximate km from fulfilment centre to destination
courier_partner           : Carrier name (Amazon Logistics, Delhivery, etc.)
shipping_cost             : Actual INR cost of shipment
expected_delivery_days    : SLA based on tier + service level
delay_probability         : Probability order is delayed (0–1)
fuel_surcharge            : INR fuel levy added to shipping cost
shipping_insurance        : INR insurance cost on order value

Why these columns don't exist in public datasets
-------------------------------------------------
Carrier contracts, rate cards, and zone matrices are negotiated
confidentially.  Revealing them discloses logistics spend and margin.
"""

import numpy as np
import pandas as pd

from config import CFG, classify_state_tier, get_shipping_rate, get_avg_distance, get_tier_surcharge


_COURIER_MAP = CFG["courier_partners"]
_FUEL_PCT = CFG["fuel_surcharge_pct"]
_INS_PCT = CFG["insurance_rate_pct"]


def _pick_courier(fulfilment: str, tier: str, rng: np.random.Generator) -> str:
    options = _COURIER_MAP.get(fulfilment, _COURIER_MAP["Merchant"])
    n = len(options)
    if n == 1:
        return options[0]
    # Tier-1 → more likely to use primary courier; distribute remaining equally
    primary_weight = 0.7
    rest = (1 - primary_weight) / (n - 1)
    weights = [primary_weight] + [rest] * (n - 1)
    return rng.choice(options, p=weights)


def _expected_delivery(tier: str, service_level: str) -> int:
    """
    SLA in days.

    tier1 + Standard → 3–4 days
    tier2 + Standard → 5–6 days
    tier3 + Standard → 7–10 days
    Expedited knocks 1 day off.
    """
    base = {"tier1": 3, "tier2": 5, "tier3": 8}[tier]
    if str(service_level).lower() == "expedited":
        base = max(1, base - 1)
    return base


def _delay_probability(tier: str, courier: str, qty: float) -> float:
    """
    Probability of delivery delay.

    Business logic:
    - Remote regions (tier3) → higher delay risk
    - Higher quantity → more handling, higher delay
    - Amazon Logistics is more reliable than 3PL
    """
    base = {"tier1": 0.05, "tier2": 0.10, "tier3": 0.20}[tier]
    qty_factor = min((qty - 1) * 0.02, 0.10)
    courier_factor = 0.0 if courier == "Amazon Logistics" else 0.05
    return round(min(base + qty_factor + courier_factor, 0.60), 4)


def run(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    df = df.copy()

    # ── Tier classification ───────────────────────────────────────────────────
    df["warehouse_zone"] = df["ship-state"].apply(classify_state_tier)

    # ── Estimated shipping distance ────────────────────────────────────────────
    # Formula: avg_distance(tier) × jitter(0.8–1.2) to reflect real variation
    def _distance(tier: str) -> float:
        base = get_avg_distance(tier)
        jitter = rng.uniform(0.80, 1.20)
        return round(base * jitter, 0)

    df["estimated_shipping_distance"] = df["warehouse_zone"].apply(_distance)

    # ── Courier partner ────────────────────────────────────────────────────────
    df["courier_partner"] = df.apply(
        lambda r: _pick_courier(r["Fulfilment"], r["warehouse_zone"], rng), axis=1
    )

    # ── Shipping cost ──────────────────────────────────────────────────────────
    # Formula:
    #   base_cost = weight_kg × qty × rate_per_kg(fulfilment)
    #   tier_surcharge = base_cost × tier_surcharge_pct
    #   shipping_cost = base_cost + tier_surcharge
    weight_kg = df["Category"].map(
        {k: v for k, v in CFG["category_weight_kg"].items()}
    ).fillna(CFG["category_weight_kg"]["default"])

    qty = df["Qty"].fillna(1).clip(lower=1)
    rate = df["Fulfilment"].map(
        {k: v for k, v in CFG["shipping_rate_per_kg"].items()}
    ).fillna(CFG["shipping_rate_per_kg"]["default"])
    surcharge_pct = df["warehouse_zone"].apply(get_tier_surcharge)

    base_shipping = weight_kg * qty * rate
    df["shipping_cost"] = (base_shipping * (1 + surcharge_pct)).round(2)

    # ── Fuel surcharge ────────────────────────────────────────────────────────
    df["fuel_surcharge"] = (df["shipping_cost"] * _FUEL_PCT).round(2)

    # ── Shipping insurance ────────────────────────────────────────────────────
    df["shipping_insurance"] = (df["Amount"].fillna(0) * _INS_PCT).round(2)

    # ── Expected delivery days ────────────────────────────────────────────────
    df["expected_delivery_days"] = df.apply(
        lambda r: _expected_delivery(r["warehouse_zone"], r.get("ship-service-level", "Standard")),
        axis=1
    )

    # ── Delay probability ─────────────────────────────────────────────────────
    df["delay_probability"] = df.apply(
        lambda r: _delay_probability(r["warehouse_zone"], r["courier_partner"], r["Qty"]),
        axis=1
    )

    return df
