"""
Module 2 — Customer Analytics
Enterprise Profit Intelligence Platform
Business Goal: Understand customer behaviour, value, and profitability.
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
SEGMENT_PALETTE: dict[str, str] = {
    "Champion":        "#1A7A4A",
    "Loyal":           "#1F3A5F",
    "Potential_Loyal": "#E67E22",
    "At_Risk":         "#C0392B",
}

REQUIRED_COLS = [
    "customer_segment", "acquisition_channel", "repeat_customer_flag",
    "estimated_clv", "estimated_cac", "loyalty_score",
    "Amount", "net_profit", "Order ID", "return_probability", "Date",
]

log = setup_logging(__name__)


# ── Analysis 1: Segment profitability ────────────────────────────────────────
def segment_profitability(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue, profit, CLV, CAC, and loyalty score by customer segment."""
    seg = df.groupby("customer_segment").agg(
        Revenue     =("Amount",        "sum"),
        Net_Profit  =("net_profit",    "sum"),
        Orders      =("Order ID",      "count"),
        Avg_CLV     =("estimated_clv", "mean"),
        Avg_CAC     =("estimated_cac", "mean"),
        Avg_Loyalty =("loyalty_score", "mean"),
    ).reset_index()
    seg["Net_Margin_Pct"] = seg["Net_Profit"] / seg["Revenue"] * 100
    seg["CLV_CAC_Ratio"]  = seg["Avg_CLV"]    / seg["Avg_CAC"]
    return seg.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_segment_profitability(seg_df: pd.DataFrame) -> None:
    """Net profit per segment and CLV vs CAC comparison — side-by-side bars."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    colors = [SEGMENT_PALETTE.get(s, COLORS["gray"]) for s in seg_df["customer_segment"]]

    bars = axes[0].bar(seg_df["customer_segment"], seg_df["Net_Profit"] / 1_000_000,
                       color=colors, edgecolor="white")
    axes[0].axhline(0, color="#555555", linewidth=0.8)
    for bar, val in zip(bars, seg_df["Net_Profit"]):
        axes[0].text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + (0.01 if val >= 0 else -0.05),
                     f"₹{val / 1_000_000:.2f}M", ha="center", fontsize=9, fontweight="bold")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[0].set_title("Net Profit by Customer Segment")
    axes[0].set_ylabel("Net Profit (INR)")

    x, w = np.arange(len(seg_df)), 0.35
    axes[1].bar(x - w / 2, seg_df["Avg_CLV"] / 1_000, width=w,
                label="Avg CLV", color=COLORS["blue"], alpha=0.85)
    axes[1].bar(x + w / 2, seg_df["Avg_CAC"] / 1_000, width=w,
                label="Avg CAC", color=COLORS["orange"], alpha=0.85)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(seg_df["customer_segment"], rotation=15)
    axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))
    axes[1].set_title("Avg CLV vs CAC by Segment")
    axes[1].set_ylabel("Amount (INR)")
    axes[1].legend()

    plt.suptitle("Customer Segment Profitability", fontsize=15, fontweight="bold", y=1.01)
    save_chart("07_segment_profitability.png")


# ── Analysis 2: Acquisition channel performance ───────────────────────────────
def channel_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue, profit, CAC, and order count by acquisition channel."""
    ch = df.groupby("acquisition_channel").agg(
        Revenue    =("Amount",        "sum"),
        Net_Profit =("net_profit",    "sum"),
        Orders     =("Order ID",      "count"),
        Avg_CAC    =("estimated_cac", "mean"),
    ).reset_index()
    ch["Net_Margin_Pct"]    = ch["Net_Profit"] / ch["Revenue"] * 100
    ch["Revenue_Per_Order"] = ch["Revenue"]    / ch["Orders"]
    return ch.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_channel_performance(ch_df: pd.DataFrame) -> None:
    """Net profit and margin % by acquisition channel — bar chart with data labels."""
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in ch_df["Net_Profit"]]
    bars = ax.bar(ch_df["acquisition_channel"], ch_df["Net_Profit"] / 1_000_000,
                  color=colors, edgecolor="white")
    ax.axhline(0, color="#555555", linewidth=0.8)
    for bar, val, margin in zip(bars, ch_df["Net_Profit"], ch_df["Net_Margin_Pct"]):
        ypos = bar.get_height() + (0.005 if val >= 0 else -0.02)
        ax.text(bar.get_x() + bar.get_width() / 2, ypos,
                f"₹{val / 1e6:.2f}M\n({margin:.1f}%)",
                ha="center", fontsize=9, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title("Net Profit & Margin by Acquisition Channel")
    ax.set_ylabel("Net Profit (INR)")
    ax.set_xlabel("Acquisition Channel")
    save_chart("08_channel_performance.png")


# ── Analysis 3: Repeat vs new customer comparison ────────────────────────────
def repeat_customer_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compare revenue, profit, order value, CLV, and return probability for repeat vs new."""
    df = df.copy()
    df["customer_type"] = df["repeat_customer_flag"].map({1: "Repeat", 0: "New"})
    rc = df.groupby("customer_type").agg(
        Revenue         =("Amount",             "sum"),
        Net_Profit      =("net_profit",         "sum"),
        Orders          =("Order ID",           "count"),
        Avg_Order_Value =("Amount",             "mean"),
        Avg_CLV         =("estimated_clv",      "mean"),
        Return_Prob     =("return_probability", "mean"),
    ).reset_index()
    rc["Net_Margin_Pct"] = rc["Net_Profit"] / rc["Revenue"] * 100
    return rc


def plot_repeat_vs_new(rc_df: pd.DataFrame) -> None:
    """Four-KPI side-by-side bar comparison: repeat vs new customers."""
    metrics = ["Revenue", "Net_Profit", "Avg_Order_Value", "Avg_CLV"]
    titles  = ["Revenue", "Net Profit", "Avg Order Value", "Avg CLV"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 5))
    palette = [COLORS["blue"], COLORS["orange"]]

    for ax, metric, title in zip(axes, metrics, titles):
        vals   = rc_df[metric]
        scaled = vals / 1_000 if vals.max() > 10_000 else vals
        unit   = "₹K" if vals.max() > 10_000 else "₹"
        ax.bar(rc_df["customer_type"], scaled, color=palette, edgecolor="white")
        ax.set_title(title)
        ax.set_ylabel(unit)

    plt.suptitle("Repeat vs New Customer Comparison", fontsize=15, fontweight="bold", y=1.01)
    save_chart("09_repeat_vs_new_customers.png")


# ── Analysis 4: CLV distribution by segment ───────────────────────────────────
def plot_clv_distribution(df: pd.DataFrame) -> None:
    """Box plot: CLV spread across customer segments to show value concentration."""
    segments = df["customer_segment"].unique()
    clv_data = [df[df["customer_segment"] == s]["estimated_clv"].dropna() / 1_000
                for s in segments]
    colors   = [SEGMENT_PALETTE.get(s, COLORS["gray"]) for s in segments]

    fig, ax = plt.subplots(figsize=(12, 5))
    bp = ax.boxplot(clv_data, tick_labels=segments, patch_artist=True,
                    medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    ax.set_title("CLV Distribution by Customer Segment")
    ax.set_ylabel("Estimated CLV (₹ Thousands)")
    ax.set_xlabel("Customer Segment")
    save_chart("10_clv_distribution.png")


# ── Analysis 5: Monthly orders by segment ────────────────────────────────────
def plot_segment_monthly_trend(df: pd.DataFrame) -> None:
    """Monthly order volume per segment — identifies growth and at-risk patterns."""
    trend = df[df["month"].astype(str) != "2022-03"]
    pivot = (trend.groupby(["month", "customer_segment"])["Order ID"]
             .count().unstack(fill_value=0))
    pivot.index = pivot.index.astype(str)

    fig, ax = plt.subplots(figsize=(12, 5))
    for seg in pivot.columns:
        ax.plot(pivot.index, pivot[seg], marker="o", linewidth=2,
                label=seg, color=SEGMENT_PALETTE.get(seg, COLORS["gray"]))

    ax.set_title("Monthly Order Volume by Customer Segment")
    ax.set_ylabel("Number of Orders")
    ax.set_xlabel("Month")
    ax.legend()
    save_chart("11_segment_monthly_trend.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(seg_df: pd.DataFrame, ch_df: pd.DataFrame,
                  rc_df: pd.DataFrame) -> None:
    """Save three customer summary tables to REPORT_DIR."""
    seg_df.to_csv(REPORT_DIR / "customer_segment_summary.csv",   index=False)
    ch_df.to_csv(REPORT_DIR  / "acquisition_channel_summary.csv", index=False)
    rc_df.to_csv(REPORT_DIR  / "repeat_vs_new_summary.csv",      index=False)
    log.info("  Saved: customer_segment_summary.csv | acquisition_channel_summary.csv | repeat_vs_new_summary.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(seg_df: pd.DataFrame, ch_df: pd.DataFrame,
                   rc_df: pd.DataFrame, df: pd.DataFrame) -> str:
    """Build customer insight text with best/worst comparisons and potential improvements."""
    best_seg    = seg_df.iloc[0]["customer_segment"]
    worst_seg   = seg_df.iloc[-1]["customer_segment"]
    best_np     = seg_df.iloc[0]["Net_Profit"]
    worst_np    = seg_df.iloc[-1]["Net_Profit"]
    seg_gap     = best_np - worst_np

    best_ch     = ch_df.iloc[0]["acquisition_channel"]
    worst_ch    = ch_df.iloc[-1]["acquisition_channel"]

    repeat_rev  = rc_df[rc_df["customer_type"] == "Repeat"]["Revenue"].values[0]
    new_rev     = rc_df[rc_df["customer_type"] == "New"]["Revenue"].values[0]
    repeat_pct  = repeat_rev / (repeat_rev + new_rev) * 100

    at_risk_pct = (df["customer_segment"] == "At_Risk").mean() * 100
    champ_clv   = seg_df[seg_df["customer_segment"] == "Champion"]["Avg_CLV"].values[0]
    atrisk_clv  = seg_df[seg_df["customer_segment"] == "At_Risk"]["Avg_CLV"].values[0]
    clv_gap_pct = (champ_clv - atrisk_clv) / max(atrisk_clv, 1) * 100

    lines = [
        "=" * 65,
        "  MODULE 2 — CUSTOMER ANALYTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Best segment: '{best_seg}' | Worst: '{worst_seg}'",
        f"     Profit gap between them: ₹{seg_gap / 1e6:.2f}M.",
        f"  2. Repeat customers drive {repeat_pct:.1f}% of total revenue.",
        f"  3. {at_risk_pct:.1f}% of customers are 'At_Risk' — immediate retention needed.",
        f"  4. Best acquisition channel: '{best_ch}' | Worst: '{worst_ch}'.",
        f"  5. Champion CLV is {clv_gap_pct:.0f}% higher than At_Risk CLV",
        f"     (₹{champ_clv / 1e3:.0f}K vs ₹{atrisk_clv / 1e3:.0f}K).",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. RETAIN 'At_Risk' customers ({at_risk_pct:.1f}% of base).",
        "      Win-back campaigns with personalised discounts and loyalty offers.",
        f"  R2. SCALE '{best_ch}' — highest ROI acquisition. Increase budget 20-30%.",
        "  R3. PROTECT Champions with early access, rewards, and dedicated support.",
        f"      Their CLV is {clv_gap_pct:.0f}% higher — churn cost is enormous.",
        "  R4. INCREASE repeat purchase rate via post-purchase email flows",
        "      and subscription/loyalty tier upgrades.",
        f"  R5. SHIFT spend from '{worst_ch}' — lowest profit-per-order channel.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write customer insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "customer_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: customer_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 2 customer analytics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 2 — CUSTOMER ANALYTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/5] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 2 — Customer Analytics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/5] Segment profitability ...")
    seg_df = segment_profitability(df)
    plot_segment_profitability(seg_df)

    log.info("\n[3/5] Acquisition channel performance ...")
    ch_df = channel_analysis(df)
    plot_channel_performance(ch_df)

    log.info("\n[4/5] Repeat vs new customer analysis ...")
    rc_df = repeat_customer_analysis(df)
    plot_repeat_vs_new(rc_df)
    plot_clv_distribution(df)
    plot_segment_monthly_trend(df)

    log.info("\n[5/5] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(seg_df, ch_df, rc_df)
    text = build_insights(seg_df, ch_df, rc_df, df)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 5")
    log.info("  Tables Generated: 3")
    log.info("-" * 44)


    return {"insights_text": text}


if __name__ == "__main__":
    run()
