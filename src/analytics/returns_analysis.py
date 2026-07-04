"""
Module 6 — Returns & Logistics Analytics
Enterprise Profit Intelligence Platform
Business Goal: Identify operational issues in returns and logistics affecting profitability.
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
    fmt_millions,
    load_data, save_chart, setup_logging, validate_columns,
)

# ── Module constants ──────────────────────────────────────────────────────────
HIGH_RETURN_VOL_PCT  = 20   # return reason above this % volume is flagged red
MED_RETURN_VOL_PCT   = 10   # return reason above this % volume is flagged orange
DELAY_ACCEPT_THRESH  = 0.10 # delay probability above this is a concern (10%)
HIGH_DELAY_THRESH    = 0.15 # delay probability above this is critical (15%)

STATUS_COLORS: dict[str, str] = {
    "Shipped - Delivered to Buyer": COLORS["green"],
    "Shipped":                      COLORS["blue"],
    "Cancelled":                    COLORS["red"],
    "Shipped - Returned to Seller": COLORS["orange"],
    "Shipped - Rejected by Buyer":  COLORS["gray"],
    "Shipped - Lost in Transit":    "#6C3483",
}

REQUIRED_COLS = [
    "return_reason", "refund_amount", "refurbishment_cost", "disposal_cost",
    "refund_processing_cost", "reverse_logistics_cost",
    "courier_partner", "shipping_cost", "delay_probability", "return_probability",
    "net_profit", "Status", "Amount", "Order ID", "Category", "Date",
]

log = setup_logging(__name__)


# ── Analysis 1: Return reason analysis ───────────────────────────────────────
def return_reason_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate return volume and total financial cost for each return reason."""
    returns = df[df["refund_amount"] > 0].copy()
    rr = returns.groupby("return_reason").agg(
        Count            =("Order ID",               "count"),
        Total_Refund     =("refund_amount",           "sum"),
        Refurb_Cost      =("refurbishment_cost",      "sum"),
        Disposal_Cost    =("disposal_cost",           "sum"),
        Processing_Cost  =("refund_processing_cost",  "sum"),
        Reverse_Logistics=("reverse_logistics_cost",  "sum"),
    ).reset_index()
    rr["Total_Return_Cost"] = (
        rr["Total_Refund"] + rr["Refurb_Cost"] +
        rr["Disposal_Cost"] + rr["Processing_Cost"] + rr["Reverse_Logistics"]
    )
    rr["Pct_of_Returns"] = rr["Count"] / rr["Count"].sum() * 100
    return rr.sort_values("Total_Return_Cost", ascending=False).reset_index(drop=True)


def plot_return_reasons(rr_df: pd.DataFrame) -> None:
    """Dual horizontal bar: return volume % and financial cost by reason."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    colors_vol = [
        COLORS["red"]    if v > HIGH_RETURN_VOL_PCT else
        COLORS["orange"] if v > MED_RETURN_VOL_PCT  else COLORS["gray"]
        for v in rr_df["Pct_of_Returns"]
    ]
    bars = axes[0].barh(rr_df["return_reason"], rr_df["Pct_of_Returns"],
                        color=colors_vol, edgecolor="white", height=0.6)
    for bar, val in zip(bars, rr_df["Pct_of_Returns"]):
        axes[0].text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                     f"{val:.1f}%", va="center", fontsize=9)
    axes[0].set_title("Return Volume by Reason")
    axes[0].set_xlabel("% of Total Returns")

    axes[1].barh(rr_df["return_reason"], rr_df["Total_Return_Cost"] / 1_000_000,
                 color=COLORS["red"], edgecolor="white", height=0.6)
    axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[1].set_title("Financial Cost by Return Reason")
    axes[1].set_xlabel("Total Cost (INR)")

    plt.suptitle("Return Reason Analysis — Volume & Financial Impact",
                 fontsize=15, fontweight="bold", y=1.01)
    save_chart("25_return_reason_analysis.png")


# ── Analysis 2: Courier partner performance ───────────────────────────────────
def courier_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate shipping cost, delay probability, return rate, and profit by courier."""
    cp = df.groupby("courier_partner").agg(
        Shipments          =("Order ID",            "count"),
        Total_Shipping_Cost=("shipping_cost",        "sum"),
        Avg_Shipping_Cost  =("shipping_cost",        "mean"),
        Avg_Delay_Prob     =("delay_probability",    "mean"),
        Return_Rate        =("return_probability",   "mean"),
        Net_Profit         =("net_profit",            "sum"),
    ).reset_index()
    cp["Cost_Per_Shipment"] = cp["Total_Shipping_Cost"] / cp["Shipments"]
    return cp.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_courier_performance(cp_df: pd.DataFrame) -> None:
    """Avg shipping cost and delay probability per courier — colour-coded by risk level."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    colors = [
        COLORS["green"]  if v < DELAY_ACCEPT_THRESH else
        COLORS["orange"] if v < HIGH_DELAY_THRESH   else COLORS["red"]
        for v in cp_df["Avg_Delay_Prob"]
    ]

    axes[0].bar(cp_df["courier_partner"], cp_df["Avg_Shipping_Cost"],
                color=COLORS["blue"], edgecolor="white", alpha=0.85)
    axes[0].set_xticks(range(len(cp_df)))
    axes[0].set_xticklabels(cp_df["courier_partner"], rotation=25, ha="right")
    axes[0].set_title("Avg Shipping Cost by Courier Partner")
    axes[0].set_ylabel("Avg Shipping Cost (₹)")

    bars = axes[1].bar(cp_df["courier_partner"], cp_df["Avg_Delay_Prob"] * 100,
                       color=colors, edgecolor="white")
    axes[1].axhline(DELAY_ACCEPT_THRESH * 100, color=COLORS["red"], linestyle="--",
                    linewidth=1, label=f"{DELAY_ACCEPT_THRESH*100:.0f}% acceptable threshold")
    for bar, val in zip(bars, cp_df["Avg_Delay_Prob"]):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                     f"{val * 100:.1f}%", ha="center", fontsize=9, fontweight="bold")
    axes[1].set_xticks(range(len(cp_df)))
    axes[1].set_xticklabels(cp_df["courier_partner"], rotation=25, ha="right")
    axes[1].set_title("Delivery Delay Probability by Courier")
    axes[1].set_ylabel("Avg Delay Probability (%)")
    axes[1].legend()

    plt.suptitle("Courier Partner Performance", fontsize=15, fontweight="bold", y=1.01)
    save_chart("26_courier_performance.png")


# ── Analysis 3: Return cost breakdown ────────────────────────────────────────
def plot_return_cost_breakdown(df: pd.DataFrame) -> None:
    """Stacked bar: five components of total return cost by category."""
    returns = df[df["refund_amount"] > 0]
    cost_cols = {
        "Refund":          "refund_amount",
        "Refurb":          "refurbishment_cost",
        "Disposal":        "disposal_cost",
        "Processing":      "refund_processing_cost",
        "Rev. Logistics":  "reverse_logistics_cost",
    }
    cat_costs = returns.groupby("Category")[list(cost_cols.values())].sum() / 1_000_000
    cat_costs.columns = list(cost_cols.keys())

    fig, ax = plt.subplots(figsize=(13, 6))
    bottom = np.zeros(len(cat_costs))
    bar_colors = [COLORS["red"], COLORS["orange"], COLORS["gray"],
                  COLORS["blue"], COLORS["green"]]

    for (label, col_vals), color in zip(cat_costs.items(), bar_colors):
        ax.bar(cat_costs.index, col_vals, bottom=bottom, label=label,
               color=color, edgecolor="white", alpha=0.85)
        bottom += col_vals.values

    ax.set_xticks(range(len(cat_costs)))
    ax.set_xticklabels(cat_costs.index, rotation=30, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title("Return Cost Breakdown by Category")
    ax.set_ylabel("Total Cost (INR)")
    ax.legend(loc="upper right")
    save_chart("27_return_cost_breakdown.png")


# ── Analysis 4: Order status funnel ──────────────────────────────────────────
def order_status_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order count, revenue, and net profit by order status."""
    status = df.groupby("Status").agg(
        Orders     =("Order ID",    "count"),
        Revenue    =("Amount",      "sum"),
        Net_Profit =("net_profit",  "sum"),
    ).reset_index()
    status["Order_Pct"] = status["Orders"] / status["Orders"].sum() * 100
    return status.sort_values("Orders", ascending=False).reset_index(drop=True)


def plot_order_status(status_df: pd.DataFrame) -> None:
    """Pie chart and bar chart: order status distribution and net profit per status."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    colors = [STATUS_COLORS.get(s, COLORS["gray"]) for s in status_df["Status"]]
    axes[0].pie(status_df["Order_Pct"], labels=status_df["Status"],
                colors=colors, autopct="%1.1f%%", startangle=140,
                wedgeprops=dict(edgecolor="white", linewidth=1.2))
    axes[0].set_title("Order Status Distribution")

    axes[1].barh(
        status_df["Status"],
        status_df["Net_Profit"] / 1_000_000,
        color=[COLORS["green"] if v >= 0 else COLORS["red"] for v in status_df["Net_Profit"]],
        edgecolor="white",
    )
    axes[1].axvline(0, color="#555555", linewidth=0.8)
    axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[1].set_title("Net Profit by Order Status")
    axes[1].set_xlabel("Net Profit (INR)")

    plt.suptitle("Order Status Analysis", fontsize=15, fontweight="bold", y=1.01)
    save_chart("28_order_status.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(rr_df: pd.DataFrame, cp_df: pd.DataFrame,
                  status_df: pd.DataFrame) -> None:
    """Save three logistics summary tables to REPORT_DIR."""
    rr_df.to_csv(REPORT_DIR     / "return_reason_summary.csv", index=False)
    cp_df.to_csv(REPORT_DIR     / "courier_performance.csv",   index=False)
    status_df.to_csv(REPORT_DIR / "order_status_summary.csv",  index=False)
    log.info("  Saved: return_reason_summary.csv | courier_performance.csv | order_status_summary.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(rr_df: pd.DataFrame, cp_df: pd.DataFrame,
                   df: pd.DataFrame) -> str:
    """Build returns insight text with top reason %, cost target, and courier comparison."""
    top_reason      = rr_df.iloc[0]["return_reason"]
    top_reason_pct  = rr_df.iloc[0]["Pct_of_Returns"]
    total_refund    = df["refund_amount"].sum()
    total_ret_cost  = rr_df["Total_Return_Cost"].sum()
    saving_20pct    = total_ret_cost * 0.20  # target: 20% reduction

    best_courier    = cp_df.iloc[0]["courier_partner"]
    worst_delay_row = cp_df.sort_values("Avg_Delay_Prob", ascending=False).iloc[0]
    best_delay_row  = cp_df.sort_values("Avg_Delay_Prob").iloc[0]
    delay_gap       = worst_delay_row["Avg_Delay_Prob"] - best_delay_row["Avg_Delay_Prob"]

    cancelled_pct   = (df["Status"] == "Cancelled").mean() * 100
    delivered_pct   = (df["Status"] == "Shipped - Delivered to Buyer").mean() * 100

    lines = [
        "=" * 65,
        "  MODULE 6 — RETURNS & LOGISTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Top return reason: '{top_reason}' ({top_reason_pct:.1f}% of all returns).",
        f"  2. Total refund value: ₹{total_refund / 1e6:.2f}M.",
        f"  3. Total return cost (refund + ops): ₹{total_ret_cost / 1e6:.2f}M.",
        f"  4. {cancelled_pct:.1f}% of orders cancelled — major revenue leak.",
        f"  5. Only {delivered_pct:.1f}% of orders reach successful delivery.",
        f"  6. Best courier: '{best_courier}' (highest profit contribution).",
        f"  7. Delay gap: '{worst_delay_row['courier_partner']}' is "
        f"{delay_gap * 100:.1f} pp worse than best courier.",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. SOLVE '{top_reason}' (#{1} return cause): size guides + fit advisor.",
        f"  R2. REDUCE cancellations from {cancelled_pct:.1f}% with prepaid incentives.",
        f"  R3. REVIEW '{worst_delay_row['courier_partner']}' SLA — "
        f"{delay_gap * 100:.1f} pp delay gap vs best partner.",
        f"  R4. TARGET 20% return cost reduction = ₹{saving_20pct / 1e6:.2f}M savings.",
        "      Better demand forecasting + pre-shipment quality checks.",
        f"  R5. IMPROVE product content to reduce wrong-item returns.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write returns insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "returns_logistics_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: returns_logistics_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 6 returns and logistics analytics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 6 — RETURNS & LOGISTICS ANALYTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/5] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 6 — Returns & Logistics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/5] Return reason analysis ...")
    rr_df = return_reason_analysis(df)
    plot_return_reasons(rr_df)
    plot_return_cost_breakdown(df)

    log.info("\n[3/5] Courier & logistics performance ...")
    cp_df = courier_performance(df)
    plot_courier_performance(cp_df)

    log.info("\n[4/5] Order status analysis ...")
    status_df = order_status_summary(df)
    plot_order_status(status_df)

    log.info("\n[5/5] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(rr_df, cp_df, status_df)
    text = build_insights(rr_df, cp_df, df)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 4")
    log.info("  Tables Generated: 3")
    log.info("-" * 44)


    return {"insights_text": text}


if __name__ == "__main__":
    run()
