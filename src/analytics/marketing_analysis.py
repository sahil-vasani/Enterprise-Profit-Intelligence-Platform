"""
Module 5 — Marketing Analytics
Enterprise Profit Intelligence Platform
Business Goal: Measure marketing effectiveness and ROI by campaign and channel.
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
MIN_GOOD_ROI    = 1.5   # campaigns below this ROI are underperforming
BREAK_EVEN_ROI  = 1.0   # campaigns below this ROI destroy profit

CAMPAIGN_PALETTE: dict[str, str] = {
    "Seasonal_Promotion":    "#1F3A5F",
    "Organic":               "#1A7A4A",
    "Amazon_PLCC_Financing": "#E67E22",
}

REQUIRED_COLS = [
    "campaign_name", "Amount", "net_profit", "Order ID",
    "campaign_cost", "discount_cost", "attributed_revenue",
    "campaign_roi", "marketing_attribution_cost",
    "acquisition_channel", "estimated_cac", "Date",
]

log = setup_logging(__name__)


# ── Analysis 1: Campaign ROI comparison ──────────────────────────────────────
def campaign_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue, profit, spend, and ROI by campaign."""
    camp = df.groupby("campaign_name").agg(
        Revenue             =("Amount",                   "sum"),
        Net_Profit          =("net_profit",                "sum"),
        Orders              =("Order ID",                "count"),
        Total_Campaign_Cost =("campaign_cost",             "sum"),
        Total_Discount_Cost =("discount_cost",             "sum"),
        Attributed_Revenue  =("attributed_revenue",        "sum"),
        Avg_ROI             =("campaign_roi",              "mean"),
        Attribution_Cost    =("marketing_attribution_cost","sum"),
    ).reset_index()
    camp["Total_Marketing_Spend"] = (
        camp["Total_Campaign_Cost"] + camp["Total_Discount_Cost"]
    )
    camp["Net_Margin_Pct"]        = camp["Net_Profit"] / camp["Revenue"] * 100
    camp["Revenue_Per_INR_Spent"] = (
        camp["Revenue"] / camp["Total_Marketing_Spend"].replace(0, np.nan)
    )
    return camp.sort_values("Avg_ROI", ascending=False).reset_index(drop=True)


def plot_campaign_roi(camp_df: pd.DataFrame) -> None:
    """Bar chart: campaign ROI vs good/break-even thresholds — green/red coded."""
    colors = [COLORS["green"] if v >= MIN_GOOD_ROI else COLORS["red"]
              for v in camp_df["Avg_ROI"]]

    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.bar(camp_df["campaign_name"], camp_df["Avg_ROI"],
                  color=colors, edgecolor="white")
    ax.axhline(MIN_GOOD_ROI, color=COLORS["orange"], linestyle="--",
               linewidth=1.5, label=f"Minimum Good ROI ({MIN_GOOD_ROI}x)")
    ax.axhline(BREAK_EVEN_ROI, color=COLORS["red"], linestyle=":",
               linewidth=1, label=f"Break-Even ({BREAK_EVEN_ROI}x)")
    for bar, val in zip(bars, camp_df["Avg_ROI"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.2f}x", ha="center", fontsize=10, fontweight="bold")
    ax.set_title("Campaign ROI Comparison")
    ax.set_ylabel("Average ROI (x)")
    ax.set_xlabel("Campaign")
    ax.legend()
    save_chart("21_campaign_roi.png")


# ── Analysis 2: Revenue vs marketing spend ────────────────────────────────────
def plot_revenue_vs_spend(camp_df: pd.DataFrame) -> None:
    """Grouped bars: revenue, net profit, and marketing spend per campaign side-by-side."""
    fig, ax = plt.subplots(figsize=(12, 5))
    x, w = np.arange(len(camp_df)), 0.3

    ax.bar(x - w / 2, camp_df["Revenue"]              / 1_000_000, width=w,
           label="Revenue",         color=COLORS["blue"],   alpha=0.85, edgecolor="white")
    ax.bar(x,          camp_df["Net_Profit"]           / 1_000_000, width=w,
           label="Net Profit",      color=COLORS["green"],  alpha=0.85, edgecolor="white")
    ax.bar(x + w / 2, camp_df["Total_Marketing_Spend"] / 1_000_000, width=w,
           label="Marketing Spend", color=COLORS["orange"], alpha=0.85, edgecolor="white")

    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(camp_df["campaign_name"], rotation=15)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title("Revenue vs Net Profit vs Marketing Spend by Campaign")
    ax.set_ylabel("Amount (INR)")
    ax.legend()
    save_chart("22_revenue_vs_spend.png")


# ── Analysis 3: Marketing cost breakdown ─────────────────────────────────────
def plot_marketing_cost_breakdown(camp_df: pd.DataFrame) -> None:
    """Stacked bar: campaign cost vs discount cost per campaign."""
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(camp_df))

    ax.bar(x, camp_df["Total_Campaign_Cost"] / 1_000_000,
           label="Campaign Cost", color=COLORS["blue"],   edgecolor="white")
    ax.bar(x, camp_df["Total_Discount_Cost"] / 1_000_000,
           bottom=camp_df["Total_Campaign_Cost"] / 1_000_000,
           label="Discount Cost", color=COLORS["orange"], edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(camp_df["campaign_name"], rotation=15)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title("Marketing Cost Breakdown — Campaign Cost vs Discount Cost")
    ax.set_ylabel("Amount (INR)")
    ax.legend()
    save_chart("23_marketing_cost_breakdown.png")


# ── Analysis 4: Acquisition channel performance ───────────────────────────────
def acquisition_channel_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate profit, revenue, orders, and CAC by acquisition channel."""
    ch = df.groupby("acquisition_channel").agg(
        Revenue    =("Amount",       "sum"),
        Net_Profit =("net_profit",   "sum"),
        Orders     =("Order ID",     "count"),
        Avg_CAC    =("estimated_cac","mean"),
    ).reset_index()
    ch["Revenue_Per_Order"] = ch["Revenue"]    / ch["Orders"]
    ch["Profit_Per_Order"]  = ch["Net_Profit"] / ch["Orders"]
    return ch.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_channel_roi(ch_df: pd.DataFrame) -> None:
    """Net profit (bars) and avg CAC (twin-axis bars) by acquisition channel."""
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in ch_df["Net_Profit"]]
    x, w = np.arange(len(ch_df)), 0.35

    ax.bar(x - w / 2, ch_df["Net_Profit"] / 1_000_000, width=w,
           label="Net Profit", color=colors, edgecolor="white")

    ax2 = ax.twinx()
    ax2.bar(x + w / 2, ch_df["Avg_CAC"] / 1_000, width=w,
            label="Avg CAC (₹K)", color=COLORS["orange"], alpha=0.7, edgecolor="white")
    ax2.set_ylabel("Avg CAC (₹ Thousands)", color=COLORS["orange"])
    ax2.tick_params(axis="y", labelcolor=COLORS["orange"])
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))

    ax.set_xticks(x)
    ax.set_xticklabels(ch_df["acquisition_channel"], rotation=20, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title("Net Profit vs Avg CAC by Acquisition Channel")
    ax.set_ylabel("Net Profit (INR)")
    ax.axhline(0, color="#555555", linewidth=0.8)

    lines1, l1 = ax.get_legend_handles_labels()
    lines2, l2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, l1 + l2, loc="upper right")
    save_chart("24_channel_roi.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(camp_df: pd.DataFrame, ch_df: pd.DataFrame) -> None:
    """Save two marketing summary tables to REPORT_DIR."""
    camp_df.to_csv(REPORT_DIR / "campaign_performance.csv",      index=False)
    ch_df.to_csv(REPORT_DIR   / "channel_marketing_summary.csv", index=False)
    log.info("  Saved: campaign_performance.csv | channel_marketing_summary.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(camp_df: pd.DataFrame, ch_df: pd.DataFrame,
                   df: pd.DataFrame) -> str:
    """Build marketing insight text with ROI gap, underperforming campaigns, and channel ranking."""
    best_camp    = camp_df.iloc[0]["campaign_name"]
    worst_camp   = camp_df.iloc[-1]["campaign_name"]
    best_roi     = camp_df.iloc[0]["Avg_ROI"]
    worst_roi    = camp_df.iloc[-1]["Avg_ROI"]
    roi_gap      = best_roi - worst_roi

    total_spend  = camp_df["Total_Marketing_Spend"].sum()
    total_rev    = camp_df["Revenue"].sum()
    overall_roi  = total_rev / total_spend if total_spend > 0 else 0
    best_ch      = ch_df.iloc[0]["acquisition_channel"]
    worst_ch     = ch_df.iloc[-1]["acquisition_channel"]

    underperforming = camp_df[camp_df["Avg_ROI"] < MIN_GOOD_ROI]["campaign_name"].tolist()
    wasted_spend    = camp_df[camp_df["Avg_ROI"] < BREAK_EVEN_ROI]["Total_Marketing_Spend"].sum()

    lines = [
        "=" * 65,
        "  MODULE 5 — MARKETING ANALYTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Best campaign: '{best_camp}' at {best_roi:.2f}x ROI.",
        f"  2. Worst campaign: '{worst_camp}' at {worst_roi:.2f}x ROI.",
        f"     ROI gap between best and worst: {roi_gap:.2f}x.",
        f"  3. Portfolio ROI: {overall_roi:.2f}x (₹{total_spend/1e6:.1f}M spend → ₹{total_rev/1e6:.1f}M revenue).",
        f"  4. Underperforming (ROI < {MIN_GOOD_ROI}x): {', '.join(underperforming) or 'None'}.",
        f"  5. Best channel: '{best_ch}' | Worst: '{worst_ch}' (highest CAC vs return).",
        f"  6. Spend on break-even or worse campaigns: ₹{wasted_spend/1e6:.2f}M.",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. SCALE '{best_camp}' — {best_roi:.2f}x ROI is proven. Increase budget 20–30%.",
        f"  R2. PAUSE '{worst_camp}' ({worst_roi:.2f}x ROI). Restructure targeting and creative.",
        "  R3. REALLOCATE budget from low-ROI campaigns to high-ROI ones.",
        f"      ₹{wasted_spend/1e6:.2f}M in near-zero-return spend can be redirected.",
        f"  R4. GROW '{best_ch}' acquisition — highest profit-per-order channel.",
        "  R5. SET a hard floor: no campaign approved below 1.0x ROI.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write marketing insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "marketing_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: marketing_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 5 marketing analytics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 5 — MARKETING ANALYTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/4] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 5 — Marketing Analytics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/4] Campaign ROI analysis ...")
    camp_df = campaign_performance(df)
    plot_campaign_roi(camp_df)
    plot_revenue_vs_spend(camp_df)
    plot_marketing_cost_breakdown(camp_df)

    log.info("\n[3/4] Acquisition channel analysis ...")
    ch_df = acquisition_channel_revenue(df)
    plot_channel_roi(ch_df)

    log.info("\n[4/4] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(camp_df, ch_df)
    text = build_insights(camp_df, ch_df, df)
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
