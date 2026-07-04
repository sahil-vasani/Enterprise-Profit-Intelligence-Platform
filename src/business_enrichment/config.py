"""
config.py — Loads business_config.yaml and exposes typed helpers.

All simulation modules import from here.  No hardcoded values
should exist anywhere else in the codebase.
"""

import os
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "business_config.yaml"


def load_config(path: str | Path = _CONFIG_PATH) -> dict:
    """Load and return the full configuration dictionary."""
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


# Singleton — loaded once at import time
CFG = load_config()


# ── Convenience accessors ────────────────────────────────────────────────────

def get_category_margin(category: str) -> float:
    return CFG["category_margins"].get(category, CFG["category_margins"]["default"])


def get_category_weight(category: str) -> float:
    return CFG["category_weight_kg"].get(category, CFG["category_weight_kg"]["default"])


def get_platform_commission(category: str) -> float:
    return CFG["platform_commission"].get(category, CFG["platform_commission"]["default"])


def get_return_rate(category: str) -> float:
    return CFG["category_return_rate"].get(category, CFG["category_return_rate"]["default"])


def get_packaging_cost(category: str) -> float:
    return CFG["packaging_cost_per_unit"].get(category, CFG["packaging_cost_per_unit"]["default"])


def get_shipping_rate(fulfilment: str) -> float:
    return CFG["shipping_rate_per_kg"].get(fulfilment, CFG["shipping_rate_per_kg"]["default"])


def get_tier_surcharge(tier: str) -> float:
    return CFG["tier_surcharge_pct"].get(tier, 0.0)


def get_avg_distance(tier: str) -> float:
    return CFG["avg_distance_km"].get(tier, CFG["avg_distance_km"]["tier3"])


def classify_state_tier(state: str) -> str:
    """Return 'tier1', 'tier2', or 'tier3' for a given state string."""
    s = str(state).upper().strip()
    for tier, states in CFG["zone_mapping"].items():
        if s in [x.upper() for x in states]:
            return tier
    return "tier3"
