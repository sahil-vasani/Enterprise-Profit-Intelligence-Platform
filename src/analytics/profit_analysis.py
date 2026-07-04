"""
Module 1 — Profit Analysis
Enterprise Profit Intelligence Platform
Business Goal: Identify WHY profit is decreasing and WHERE profit is leaking.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from analytics.utils import (
    COLORS, DATA_PATH, REPORT_DIR,
    fmt_millions, fmt_millions_1dp, fmt_thousands, fmt_pct, fmt_pct_1dp,
    load_data, save_chart, setup_logging, validate_columns,
)

# ── Module constants ──────────────────────────────────────────────────────────
HIGH_COST_THRESHOLD   = 5_000_000   # leakage bars above this → red
MEDIUM_COST_THRESHOLD = 1_000_000   # leakage bars above this → orange
PARTIAL_MONTH         = "2022-03"   # incomplete month excluded from trend charts
TOP_LOSS_PRODUCTS_N   = 15          # number of SKUs shown in loss chart

REQUIRED_COLS = [
    "Amount", "cogs", "gross_profit", "net_profit", "profit_margin_pct",
    "platform_commission", "profit_leakage", "Category", "Date", "Order ID",
    "product_profitability_score", "SKU",
]

log = setup_logging(__name__)


# ── Analysis 1: P&L decomposition ────────────────────────────────────────────
def profit_decomposition(df: pd.DataFrame) -> dict:
    """Aggregate all P&L line items into a single summary dict."""
    return {
        "revenue":        df["Amount"].sum(),
        "cogs":           df["cogs"].sum(),
        "gross_profit":   df["gross_profit"].sum(),
        "platform_fee":   df["platform_commission"].sum(),
        "shipping":       df["shipping_cost"].sum(),
        "returns":        df["refund_amount"].sum(),
        "discount":       df["discount_cost"].sum(),
        "net_profit":     df["net_profit"].sum(),
        "net_margin_pct": df["net_profit"].sum() / df["Amount"].sum() * 100,
    }


# ── Chart 1: Waterfall chart ──────────────────────────────────────────────────
def plot_waterfall(pnl: dict) -> None:
    """Waterfall chart showing the step-by-step P&L bridge from Revenue to Net Profit."""
    labels  = ["Revenue", "COGS", "Gross Profit", "Platform Fee",
               "Shipping", "Returns", "Discounts", "Net Profit"]
    values  = [
        pnl["revenue"], -pnl["cogs"], pnl["gross_profit"],
        -pnl["platform_fee"], -pnl["shipping"], -pnl["returns"],
        -pnl["discount"], pnl["net_profit"],
    ]
    running = [0] * len(values)
    for i in range(1, len(values)):
        running[i] = running[i - 1] + values[i - 1]

    bar_colors = [
        COLORS["blue"], COLORS["red"], COLORS["green"],
        COLORS["red"], COLORS["red"], COLORS["red"],
        COLORS["red"],
        COLORS["green"] if pnl["net_profit"] >= 0 else COLORS["red"],
    ]

    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(labels, values, bottom=running, color=bar_colors,
                  edgecolor="white", width=0.6)
    ax.axhline(0, color="#555555", linewidth=0.8)
    for bar, val in zip(bars, values):
        ypos = bar.get_y() + bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                ypos + (50_000 if val >= 0 else -200_000),
                f"₹{val / 1_000_000:.2f}M",
                ha="center", fontsize=9, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions_1dp))
    ax.set_title("P&L Waterfall — Revenue to Net Profit Bridge")
    ax.set_ylabel("Amount (INR)")
    save_chart("01_profit_waterfall.png")


# ── Analysis 2: Profit leakage drivers ───────────────────────────────────────
def leakage_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Sum each profit-leakage cost driver to identify the biggest drains."""
    cost_cols = {
        "Platform Commission": "platform_commission",
        "COGS":                "cogs",
        "Shipping Cost":       "shipping_cost",
        "Refund Amount":       "refund_amount",
        "Discount Cost":       "discount_cost",
        "Warehouse Handling":  "warehouse_handling_cost",
        "Inventory Holding":   "inventory_holding_cost",
        "Campaign Cost":       "campaign_cost",
        "Reverse Logistics":   "reverse_logistics_cost",
    }
    records = [
        {"Cost Driver": label, "Total Cost": df[col].sum()}
        for label, col in cost_cols.items()
        if col in df.columns
    ]
    return (pd.DataFrame(records)
              .sort_values("Total Cost", ascending=False)
              .reset_index(drop=True))


def plot_leakage(leak_df: pd.DataFrame) -> None:
    """Horizontal bar chart: profit leakage by cost driver, colour-coded by severity."""
    colors = [
        COLORS["red"]    if v > HIGH_COST_THRESHOLD   else
        COLORS["orange"] if v > MEDIUM_COST_THRESHOLD else
        COLORS["green"]
        for v in leak_df["Total Cost"]
    ]
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(leak_df["Cost Driver"], leak_df["Total Cost"] / 1_000_000,
                   color=colors, edgecolor="white", height=0.6)
    for bar, val in zip(bars, leak_df["Total Cost"]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"₹{val / 1_000_000:.1f}M", va="center", fontsize=9)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions_1dp))
    ax.set_title("Profit Leakage by Cost Driver")
    ax.set_xlabel("Total Cost (INR)")

    legend = [
        mpatches.Patch(color=COLORS["red"],    label=f"> ₹{HIGH_COST_THRESHOLD/1e6:.0f}M (Critical)"),
        mpatches.Patch(color=COLORS["orange"], label=f"> ₹{MEDIUM_COST_THRESHOLD/1e6:.0f}M (High)"),
        mpatches.Patch(color=COLORS["green"],  label="Manageable"),
    ]
    ax.legend(handles=legend, loc="lower right")
    save_chart("02_profit_leakage_by_driver.png")


# ── Analysis 3: Category profitability ───────────────────────────────────────
def category_profit(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue and net profit by product category."""
    cat = df.groupby("Category").agg(
        Revenue    =("Amount",     "sum"),
        Net_Profit =("net_profit", "sum"),
        Orders     =("Order ID",   "count"),
    ).reset_index()
    cat["Net_Margin_Pct"] = cat["Net_Profit"] / cat["Revenue"] * 100
    return cat.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_category_profit(cat_df: pd.DataFrame) -> None:
    """Grouped bars showing revenue vs net profit per category, with margin % overlay."""
    fig, ax = plt.subplots(figsize=(14, 5))
    x, w = np.arange(len(cat_df)), 0.35

    ax.bar(x - w / 2, cat_df["Revenue"]    / 1_000_000, width=w,
           label="Revenue",    color=COLORS["blue"],  alpha=0.85, edgecolor="white")
    ax.bar(x + w / 2, cat_df["Net_Profit"] / 1_000_000, width=w,
           label="Net Profit", color=COLORS["green"], alpha=0.85, edgecolor="white")
    ax.axhline(0, color="#555555", linewidth=0.8)

    for i, (_, row) in enumerate(cat_df.iterrows()):
        color = COLORS["green"] if row["Net_Margin_Pct"] >= 0 else COLORS["red"]
        ax.text(i, max(row["Revenue"], 0) / 1_000_000 + 0.3,
                f"{row['Net_Margin_Pct']:.1f}%", ha="center",
                fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(cat_df["Category"], rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions_1dp))
    ax.set_title("Revenue vs Net Profit by Category (margin % labelled)")
    ax.set_ylabel("Amount (INR)")
    ax.legend()
    save_chart("03_category_profit.png")


# ── Analysis 4: Pareto revenue analysis ──────────────────────────────────────
def plot_pareto(cat_df: pd.DataFrame) -> None:
    """Pareto chart: cumulative revenue share — which categories drive 80% of revenue?"""
    sorted_df   = cat_df.sort_values("Revenue", ascending=False).reset_index(drop=True)
    cum_pct     = (sorted_df["Revenue"].cumsum() / sorted_df["Revenue"].sum()) * 100

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.bar(sorted_df["Category"], sorted_df["Revenue"] / 1_000_000,
            color=COLORS["blue"], alpha=0.85, edgecolor="white")
    ax1.set_ylabel("Revenue (INR)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions_1dp))
    ax1.set_xticklabels(sorted_df["Category"], rotation=30, ha="right")
    ax1.set_xticks(range(len(sorted_df)))

    ax2 = ax1.twinx()
    ax2.plot(sorted_df["Category"], cum_pct,
             color=COLORS["red"], marker="o", linewidth=2, markersize=6)
    ax2.axhline(80, color=COLORS["orange"], linestyle="--",
                linewidth=1, label="80% threshold")
    ax2.set_ylabel("Cumulative Revenue %")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_pct))
    ax2.legend(loc="lower right")

    ax1.set_title("Pareto Analysis — Revenue Concentration by Category")
    save_chart("04_pareto_revenue.png")


# ── Analysis 5: Monthly profit trend ─────────────────────────────────────────
def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly aggregation of revenue and net profit, excluding the partial month."""
    monthly = (df[df["month"].astype(str) != PARTIAL_MONTH]
               .groupby("month")
               .agg(Revenue=("Amount", "sum"), Net_Profit=("net_profit", "sum"))
               .reset_index())
    monthly["month"]          = monthly["month"].astype(str)
    monthly["Net_Margin_Pct"] = monthly["Net_Profit"] / monthly["Revenue"] * 100
    return monthly


def plot_monthly_trend(monthly_df: pd.DataFrame) -> None:
    """Dual-axis chart: monthly revenue bars with net profit margin % line overlay."""
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.bar(monthly_df["month"], monthly_df["Revenue"] / 1_000_000,
            color=COLORS["blue"], alpha=0.7, edgecolor="white", label="Revenue")
    ax1.bar(monthly_df["month"], monthly_df["Net_Profit"] / 1_000_000,
            color=COLORS["green"], alpha=0.9, edgecolor="white", label="Net Profit")
    ax1.axhline(0, color="#555555", linewidth=0.8)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions_1dp))
    ax1.set_ylabel("Amount (INR)")
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(monthly_df["month"], monthly_df["Net_Margin_Pct"],
             color=COLORS["red"], marker="o", linewidth=2, label="Net Margin %")
    ax2.axhline(0, color=COLORS["red"], linestyle="--", linewidth=0.8)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_pct_1dp))
    ax2.set_ylabel("Net Margin %", color=COLORS["red"])
    ax2.tick_params(axis="y", labelcolor=COLORS["red"])
    ax2.legend(loc="upper right")

    ax1.set_title("Monthly Revenue & Net Profit Trend")
    ax1.set_xlabel("Month")
    save_chart("05_monthly_profit_trend.png")


# ── Analysis 6: Top loss-making products ─────────────────────────────────────
def top_loss_products(df: pd.DataFrame, n: int = TOP_LOSS_PRODUCTS_N) -> pd.DataFrame:
    """Return the n SKUs with the largest cumulative net loss."""
    prod = (df.groupby("SKU")
              .agg(Net_Profit=("net_profit", "sum"), Orders=("Order ID", "count"),
                   Avg_Score=("product_profitability_score", "mean"))
              .reset_index()
              .sort_values("Net_Profit")
              .head(n))
    return prod


def plot_top_loss_products(loss_df: pd.DataFrame) -> None:
    """Horizontal bar chart of the highest-loss SKUs."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(loss_df["SKU"], loss_df["Net_Profit"] / 1_000,
            color=COLORS["red"], edgecolor="white", height=0.6)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))
    ax.set_title(f"Top {len(loss_df)} Loss-Making Products by Net Profit")
    ax.set_xlabel("Net Profit (₹K)")
    save_chart("06_top_loss_products.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(cat_df: pd.DataFrame, monthly_df: pd.DataFrame,
                  loss_df: pd.DataFrame) -> None:
    """Save three summary tables to REPORT_DIR."""
    cat_df.to_csv(REPORT_DIR    / "category_profit_summary.csv", index=False)
    monthly_df.to_csv(REPORT_DIR / "monthly_profit_summary.csv",  index=False)
    loss_df.to_csv(REPORT_DIR   / "top_loss_products.csv",        index=False)
    log.info("  Saved: category_profit_summary.csv | monthly_profit_summary.csv | top_loss_products.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(pnl: dict, leak_df: pd.DataFrame, cat_df: pd.DataFrame,
                   monthly_df: pd.DataFrame) -> str:
    """Build a concise insight + recommendation report from computed metrics."""
    best_cat    = cat_df.iloc[0]["Category"]
    worst_cat   = cat_df.iloc[-1]["Category"]
    best_margin = cat_df.iloc[0]["Net_Margin_Pct"]
    worst_margin= cat_df.iloc[-1]["Net_Margin_Pct"]
    margin_gap  = abs(best_margin - worst_margin)

    top_leak     = leak_df.iloc[0]["Cost Driver"]
    top_leak_amt = leak_df.iloc[0]["Total Cost"]
    leak_pct     = top_leak_amt / pnl["revenue"] * 100

    margin_trend = monthly_df["Net_Margin_Pct"].iloc[-1] - monthly_df["Net_Margin_Pct"].iloc[0]

    lines = [
        "=" * 65,
        "  MODULE 1 — PROFIT ANALYSIS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Net Margin: {pnl['net_margin_pct']:.2f}%  "
        f"(Revenue ₹{pnl['revenue']/1e6:.1f}M → Net ₹{pnl['net_profit']/1e6:.2f}M).",
        f"  2. Top cost driver: '{top_leak}' = ₹{top_leak_amt/1e6:.1f}M "
        f"({leak_pct:.1f}% of revenue).",
        f"  3. Best category: '{best_cat}' ({best_margin:.1f}% margin) vs "
        f"worst: '{worst_cat}' ({worst_margin:.1f}%) — gap of {margin_gap:.1f} pp.",
        f"  4. Margin trend: {'improved' if margin_trend > 0 else 'worsened'} by "
        f"{abs(margin_trend):.2f} pp over the tracked period.",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. ATTACK '{top_leak}' first — it consumes {leak_pct:.1f}% of every revenue rupee.",
        "      Renegotiate platform fee or reduce commission-heavy categories.",
        f"  R2. GROW '{best_cat}' — highest margin category. Expand SKU range and ad spend.",
        f"  R3. FIX or phase out '{worst_cat}' — drag on overall portfolio margin.",
        "      Run a 90-day profitability review: reprice, bundle, or delist.",
        "  R4. TARGET a net margin of 0% as Phase 1 goal.",
        f"      Reducing total leakage by 15% adds ~₹{pnl['net_profit']*-0.15/1e6:.1f}M to bottom line.",
        "  R5. MONITOR monthly margin trend weekly — early signal of cost creep.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "business_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: business_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 1 profit analysis pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 1 — PROFIT ANALYSIS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/6] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 1 — Profit Analysis")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/6] P&L decomposition & waterfall ...")
    pnl = profit_decomposition(df)
    plot_waterfall(pnl)

    log.info("\n[3/6] Profit leakage analysis ...")
    leak_df = leakage_analysis(df)
    plot_leakage(leak_df)

    log.info("\n[4/6] Category profitability & Pareto ...")
    cat_df = category_profit(df)
    plot_category_profit(cat_df)
    plot_pareto(cat_df)

    log.info("\n[5/6] Monthly trend & top-loss products ...")
    monthly_df = monthly_trend(df)
    plot_monthly_trend(monthly_df)
    loss_df = top_loss_products(df)
    plot_top_loss_products(loss_df)

    log.info("\n[6/6] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(cat_df, monthly_df, loss_df)
    text = build_insights(pnl, leak_df, cat_df, monthly_df)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 6")
    log.info("  Tables Generated: 3")
    log.info("-" * 44)


if __name__ == "__main__":
    run()
