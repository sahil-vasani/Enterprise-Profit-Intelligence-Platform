"""
Module 4 — Inventory Analytics
Enterprise Profit Intelligence Platform
Business Goal: Evaluate inventory efficiency and identify dead stock and replenishment needs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from analytics.utils import (
    COLORS, REPORT_DIR,
    fmt_millions, fmt_thousands,
    load_data, save_chart, setup_logging, validate_columns,
)

# ── Module constants ──────────────────────────────────────────────────────────
SLOW_STOCK_DAYS     = 30    # inventory aged beyond this is classified slow-moving
HIGH_STOCKOUT_RISK  = 0.50  # stockout probability above this triggers red alert
MED_STOCKOUT_RISK   = 0.30  # stockout probability above this triggers orange alert
HIGH_DEAD_STOCK_PCT = 0.01  # dead stock rate above this triggers red
MED_DEAD_STOCK_PCT  = 0.005 # dead stock rate above this triggers orange

TIER_COLORS: dict[str, str] = {
    "tier1": "#1F3A5F", "tier2": "#E67E22", "tier3": "#C0392B",
}

REQUIRED_COLS = [
    "warehouse_zone", "Amount", "net_profit", "Order ID",
    "inventory_turnover", "warehouse_handling_cost", "inventory_holding_cost",
    "stockout_probability", "dead_stock_flag",
    "SKU", "Category", "inventory_age_days", "Date",
]

log = setup_logging(__name__)


# ── Analysis 1: Warehouse performance comparison ──────────────────────────────
def warehouse_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate profit, turnover, inventory costs, and stockout/dead-stock rates by warehouse."""
    wh = df.groupby("warehouse_zone").agg(
        Orders              =("Order ID",                "count"),
        Revenue             =("Amount",                  "sum"),
        Net_Profit          =("net_profit",               "sum"),
        Avg_Turnover        =("inventory_turnover",       "mean"),
        Total_Handling_Cost =("warehouse_handling_cost",  "sum"),
        Total_Holding_Cost  =("inventory_holding_cost",   "sum"),
        Avg_Stockout_Prob   =("stockout_probability",     "mean"),
        Dead_Stock_Rate     =("dead_stock_flag",          "mean"),
    ).reset_index()
    wh["Total_Inventory_Cost"] = wh["Total_Handling_Cost"] + wh["Total_Holding_Cost"]
    wh["Net_Margin_Pct"]       = wh["Net_Profit"] / wh["Revenue"] * 100
    return wh.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_warehouse_comparison(wh_df: pd.DataFrame) -> None:
    """Three-panel chart: net profit, total inventory cost, and avg turnover by warehouse."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    colors = [TIER_COLORS.get(t, COLORS["gray"]) for t in wh_df["warehouse_zone"]]

    bars = axes[0].bar(wh_df["warehouse_zone"], wh_df["Net_Profit"] / 1_000_000,
                       color=colors, edgecolor="white")
    axes[0].axhline(0, color="#555555", linewidth=0.8)
    for bar, val in zip(bars, wh_df["Net_Profit"]):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                     f"₹{val / 1e6:.2f}M", ha="center", fontsize=9, fontweight="bold")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[0].set_title("Net Profit by Warehouse")
    axes[0].set_ylabel("Net Profit (INR)")

    axes[1].bar(wh_df["warehouse_zone"], wh_df["Total_Inventory_Cost"] / 1_000_000,
                color=colors, edgecolor="white")
    axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[1].set_title("Total Inventory Cost by Warehouse")
    axes[1].set_ylabel("Cost (INR)")

    axes[2].bar(wh_df["warehouse_zone"], wh_df["Avg_Turnover"],
                color=colors, edgecolor="white")
    axes[2].set_title("Avg Inventory Turnover by Warehouse")
    axes[2].set_ylabel("Turnover Ratio")

    plt.suptitle("Warehouse Performance Comparison", fontsize=15, fontweight="bold", y=1.01)
    save_chart("17_warehouse_comparison.png")


# ── Analysis 2: Dead stock analysis ──────────────────────────────────────────
def dead_stock_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate dead stock rate and holding cost by category."""
    ds = df.groupby("Category").agg(
        Total_SKUs      =("SKU",               "nunique"),
        Dead_Stock_Flag =("dead_stock_flag",   "sum"),
        Dead_Stock_Rate =("dead_stock_flag",   "mean"),
        Avg_Age_Days    =("inventory_age_days","mean"),
        Holding_Cost    =("inventory_holding_cost", "sum"),
    ).reset_index()
    ds["Dead_Stock_Rate_Pct"] = ds["Dead_Stock_Rate"] * 100
    return ds.sort_values("Dead_Stock_Rate", ascending=False).reset_index(drop=True)


def plot_dead_stock(ds_df: pd.DataFrame) -> None:
    """Dead stock rate and holding cost per category — colour-coded by severity."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    colors = [
        COLORS["red"]    if v > HIGH_DEAD_STOCK_PCT else
        COLORS["orange"] if v > MED_DEAD_STOCK_PCT  else COLORS["green"]
        for v in ds_df["Dead_Stock_Rate"]
    ]

    bars = axes[0].bar(ds_df["Category"], ds_df["Dead_Stock_Rate_Pct"],
                       color=colors, edgecolor="white")
    for bar, val in zip(bars, ds_df["Dead_Stock_Rate_Pct"]):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                     f"{val:.2f}%", ha="center", fontsize=9, fontweight="bold")
    axes[0].set_xticks(range(len(ds_df)))
    axes[0].set_xticklabels(ds_df["Category"], rotation=30, ha="right")
    axes[0].set_title("Dead Stock Rate by Category")
    axes[0].set_ylabel("Dead Stock Rate (%)")

    axes[1].bar(ds_df["Category"], ds_df["Holding_Cost"] / 1_000_000,
                color=COLORS["orange"], edgecolor="white")
    axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[1].set_xticks(range(len(ds_df)))
    axes[1].set_xticklabels(ds_df["Category"], rotation=30, ha="right")
    axes[1].set_title("Inventory Holding Cost by Category")
    axes[1].set_ylabel("Holding Cost (INR)")

    plt.suptitle("Dead Stock & Holding Cost Analysis", fontsize=15, fontweight="bold", y=1.01)
    save_chart("18_dead_stock_analysis.png")


# ── Analysis 3: Inventory age distribution ────────────────────────────────────
def plot_inventory_age(df: pd.DataFrame) -> None:
    """Histogram of inventory age — shows the proportion of slow-moving stock."""
    age      = df["inventory_age_days"].dropna()
    slow_pct = (age > SLOW_STOCK_DAYS).mean() * 100

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.hist(age, bins=40, color=COLORS["blue"], alpha=0.8, edgecolor="white")
    ax.axvline(SLOW_STOCK_DAYS, color=COLORS["red"], linestyle="--", linewidth=1.5,
               label=f"{SLOW_STOCK_DAYS}-day threshold ({slow_pct:.1f}% slow stock)")
    ax.set_title("Inventory Age Distribution — Identifying Slow-Moving Stock")
    ax.set_xlabel("Inventory Age (Days)")
    ax.set_ylabel("Number of Orders")
    ax.legend()
    save_chart("19_inventory_age_distribution.png")


# ── Analysis 4: Stockout risk by category ────────────────────────────────────
def plot_stockout_risk(df: pd.DataFrame) -> None:
    """Bar chart: avg stockout probability by category — replenishment priority signal."""
    stockout = (df.groupby("Category")["stockout_probability"]
                  .mean().sort_values(ascending=False).reset_index())
    colors = [
        COLORS["red"]    if v > HIGH_STOCKOUT_RISK else
        COLORS["orange"] if v > MED_STOCKOUT_RISK  else COLORS["green"]
        for v in stockout["stockout_probability"]
    ]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(stockout["Category"], stockout["stockout_probability"] * 100,
                  color=colors, edgecolor="white")
    ax.axhline(HIGH_STOCKOUT_RISK * 100, color=COLORS["red"], linestyle="--",
               linewidth=1, label=f"High Risk Threshold ({HIGH_STOCKOUT_RISK*100:.0f}%)")
    for bar, val in zip(bars, stockout["stockout_probability"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val * 100:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(stockout)))
    ax.set_xticklabels(stockout["Category"], rotation=30, ha="right")
    ax.set_title("Stockout Risk by Category — Replenishment Priority")
    ax.set_ylabel("Avg Stockout Probability (%)")
    ax.legend()
    save_chart("20_stockout_risk.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(wh_df: pd.DataFrame, ds_df: pd.DataFrame) -> None:
    """Save two inventory summary tables to REPORT_DIR."""
    wh_df.to_csv(REPORT_DIR / "warehouse_performance.csv", index=False)
    ds_df.to_csv(REPORT_DIR / "dead_stock_analysis.csv",   index=False)
    log.info("  Saved: warehouse_performance.csv | dead_stock_analysis.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(wh_df: pd.DataFrame, ds_df: pd.DataFrame,
                   df: pd.DataFrame) -> str:
    """Build inventory insight text with best/worst warehouse comparison and cost opportunity."""
    best_wh      = wh_df.iloc[0]["warehouse_zone"]
    worst_wh     = wh_df.iloc[-1]["warehouse_zone"]
    best_cost    = wh_df.iloc[0]["Total_Inventory_Cost"]
    worst_cost   = wh_df.iloc[-1]["Total_Inventory_Cost"]
    cost_gap     = worst_cost - best_cost

    highest_ds   = ds_df.iloc[0]["Category"]
    total_dead   = int(df["dead_stock_flag"].sum())
    dead_cost    = df[df["dead_stock_flag"] == 1]["inventory_holding_cost"].sum()
    slow_pct     = (df["inventory_age_days"] > SLOW_STOCK_DAYS).mean() * 100
    high_stock   = (df.groupby("Category")["stockout_probability"].mean()
                      .sort_values(ascending=False).index[0])

    lines = [
        "=" * 65,
        "  MODULE 4 — INVENTORY ANALYTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Best warehouse: '{best_wh}' | Worst: '{worst_wh}'",
        f"     Inventory cost gap: ₹{cost_gap / 1e6:.2f}M — optimisation opportunity.",
        f"  2. '{highest_ds}' category has the highest dead stock rate.",
        f"  3. {total_dead:,} units flagged dead stock — holding cost ₹{dead_cost / 1e6:.2f}M.",
        f"  4. {slow_pct:.1f}% of inventory exceeds {SLOW_STOCK_DAYS}-day age threshold.",
        f"  5. '{high_stock}' has highest stockout risk — urgent reorder required.",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. AUDIT '{worst_wh}' costs — ₹{cost_gap / 1e6:.2f}M gap vs best warehouse.",
        "      Consolidate slow-moving SKUs to cut handling overhead.",
        f"  R2. CLEAR {total_dead:,} dead-stock units via flash sales or bundling.",
        f"      ₹{dead_cost / 1e6:.2f}M tied up in dead inventory earns nothing.",
        f"  R3. REORDER '{high_stock}' immediately — stockouts destroy margin.",
        f"  R4. MARKDOWN stock aged > {SLOW_STOCK_DAYS} days by 15–25%.",
        "      Turn slow-movers into cash before they become dead stock.",
        "  R5. IMPLEMENT weekly inventory age alerts to catch issues early.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write inventory insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "inventory_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: inventory_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 4 inventory analytics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 4 — INVENTORY ANALYTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/5] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 4 — Inventory Analytics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/5] Warehouse performance ...")
    wh_df = warehouse_performance(df)
    plot_warehouse_comparison(wh_df)

    log.info("\n[3/5] Dead stock analysis ...")
    ds_df = dead_stock_analysis(df)
    plot_dead_stock(ds_df)

    log.info("\n[4/5] Inventory age & stockout risk ...")
    plot_inventory_age(df)
    plot_stockout_risk(df)

    log.info("\n[5/5] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(wh_df, ds_df)
    text = build_insights(wh_df, ds_df, df)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 4")
    log.info("  Tables Generated: 2")
    log.info("-" * 44)


    return {"insights_text": text}


if __name__ == "__main__":
    run()
