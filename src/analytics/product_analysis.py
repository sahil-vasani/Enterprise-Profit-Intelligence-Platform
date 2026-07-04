"""
Module 3 — Product Analytics
Enterprise Profit Intelligence Platform
Business Goal: Evaluate product performance and identify what to promote or discontinue.
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
ABC_COLORS: dict[str, str] = {"A": "#1A7A4A", "B": "#E67E22", "C": "#C0392B"}
TOP_N_PRODUCTS  = 12    # SKUs shown in top / bottom product ranking chart
HIGH_RETURN_PCT = 0.15  # return rate above this threshold is flagged red

REQUIRED_COLS = [
    "Category", "Amount", "net_profit", "Order ID", "return_probability",
    "contribution_margin", "profit_margin_pct", "abc_class", "velocity_class",
    "dead_stock_flag", "SKU", "Date",
]

log = setup_logging(__name__)


# ── Analysis 1: Category performance ─────────────────────────────────────────
def category_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue, profit, return rate, and contribution margin by category."""
    cat = df.groupby("Category").agg(
        Revenue             =("Amount",              "sum"),
        Net_Profit          =("net_profit",           "sum"),
        Orders              =("Order ID",            "count"),
        Return_Rate         =("return_probability",  "mean"),
        Contribution_Margin =("contribution_margin", "mean"),
        Avg_Margin_Pct      =("profit_margin_pct",   "mean"),
    ).reset_index()
    cat["Net_Margin_Pct"] = cat["Net_Profit"] / cat["Revenue"] * 100
    return cat.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_category_performance(cat_df: pd.DataFrame) -> None:
    """Revenue vs net profit and return rate per category — identify investment priorities."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    x, w = np.arange(len(cat_df)), 0.35

    axes[0].bar(x - w / 2, cat_df["Revenue"]    / 1_000_000, width=w,
                label="Revenue",    color=COLORS["blue"],  alpha=0.85, edgecolor="white")
    axes[0].bar(x + w / 2, cat_df["Net_Profit"] / 1_000_000, width=w,
                label="Net Profit", color=COLORS["green"], alpha=0.85, edgecolor="white")
    axes[0].axhline(0, color="#555555", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cat_df["Category"], rotation=30, ha="right")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[0].set_title("Revenue vs Net Profit by Category")
    axes[0].set_ylabel("Amount (INR)")
    axes[0].legend()

    colors = [
        COLORS["red"]    if v > HIGH_RETURN_PCT else
        COLORS["orange"] if v > 0.10            else COLORS["green"]
        for v in cat_df["Return_Rate"]
    ]
    bars = axes[1].bar(cat_df["Category"], cat_df["Return_Rate"] * 100,
                       color=colors, edgecolor="white")
    axes[1].axhline(HIGH_RETURN_PCT * 100, color=COLORS["red"], linestyle="--",
                    linewidth=1, label=f"{HIGH_RETURN_PCT*100:.0f}% threshold")
    for bar, val in zip(bars, cat_df["Return_Rate"]):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                     f"{val * 100:.1f}%", ha="center", fontsize=9, fontweight="bold")
    axes[1].set_xticks(range(len(cat_df)))
    axes[1].set_xticklabels(cat_df["Category"], rotation=30, ha="right")
    axes[1].set_title("Return Rate by Category")
    axes[1].set_ylabel("Return Rate (%)")
    axes[1].legend()

    plt.suptitle("Category Performance Overview", fontsize=15, fontweight="bold", y=1.01)
    save_chart("12_category_performance.png")


# ── Analysis 2: ABC analysis ──────────────────────────────────────────────────
def abc_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate revenue share and net profit by ABC product class."""
    abc = df.groupby("abc_class").agg(
        SKUs       =("SKU",        "nunique"),
        Revenue    =("Amount",     "sum"),
        Net_Profit =("net_profit", "sum"),
        Orders     =("Order ID",   "count"),
    ).reset_index()
    abc["Revenue_Share"]  = abc["Revenue"]    / abc["Revenue"].sum()  * 100
    abc["Net_Margin_Pct"] = abc["Net_Profit"] / abc["Revenue"]        * 100
    return abc.sort_values("abc_class").reset_index(drop=True)


def plot_abc_analysis(abc_df: pd.DataFrame) -> None:
    """Revenue share pie and net profit bars by ABC class — where is the money?"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    colors = [ABC_COLORS.get(c, COLORS["gray"]) for c in abc_df["abc_class"]]

    axes[0].pie(abc_df["Revenue_Share"], labels=abc_df["abc_class"],
                colors=colors, autopct="%1.1f%%", startangle=140,
                wedgeprops=dict(edgecolor="white", linewidth=1.5))
    axes[0].set_title("Revenue Share by ABC Class")

    bars = axes[1].bar(abc_df["abc_class"], abc_df["Net_Profit"] / 1_000_000,
                       color=colors, edgecolor="white")
    axes[1].axhline(0, color="#555555", linewidth=0.8)
    for bar, val in zip(bars, abc_df["Net_Profit"]):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                     f"₹{val / 1e6:.2f}M", ha="center", fontsize=10, fontweight="bold")
    axes[1].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    axes[1].set_title("Net Profit by ABC Class")
    axes[1].set_ylabel("Net Profit (INR)")

    plt.suptitle("ABC Product Classification Analysis", fontsize=15, fontweight="bold", y=1.01)
    save_chart("13_abc_analysis.png")


# ── Analysis 3: Velocity class profitability ──────────────────────────────────
def velocity_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate margin, return rate, and dead stock rate by velocity class."""
    vel = df.groupby("velocity_class").agg(
        Revenue    =("Amount",             "sum"),
        Net_Profit =("net_profit",         "sum"),
        Orders     =("Order ID",           "count"),
        Return_Rate=("return_probability", "mean"),
        Dead_Stock =("dead_stock_flag",    "mean"),
    ).reset_index()
    vel["Net_Margin_Pct"] = vel["Net_Profit"] / vel["Revenue"] * 100
    return vel.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_velocity_analysis(vel_df: pd.DataFrame) -> None:
    """Net margin vs dead stock rate by velocity class — twin-axis comparison."""
    vel_order = ["Fast", "Medium", "Slow"]
    vel_df    = vel_df.set_index("velocity_class").reindex(vel_order).reset_index()

    fig, ax = plt.subplots(figsize=(11, 5))
    x, w = np.arange(len(vel_df)), 0.3
    ax.bar(x - w / 2, vel_df["Net_Margin_Pct"], width=w,
           label="Net Margin %", color=COLORS["blue"], alpha=0.85)
    ax.axhline(0, color="#555555", linewidth=0.8)

    ax2 = ax.twinx()
    ax2.bar(x + w / 2, vel_df["Dead_Stock"] * 100, width=w,
            label="Dead Stock %", color=COLORS["red"], alpha=0.7)
    ax2.set_ylabel("Dead Stock Rate (%)", color=COLORS["red"])
    ax2.tick_params(axis="y", labelcolor=COLORS["red"])

    ax.set_xticks(x)
    ax.set_xticklabels(vel_df["velocity_class"])
    ax.set_ylabel("Net Margin (%)")
    ax.set_title("Velocity Class — Net Margin vs Dead Stock Rate")

    lines1, l1 = ax.get_legend_handles_labels()
    lines2, l2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, l1 + l2, loc="upper right")
    save_chart("14_velocity_analysis.png")


# ── Analysis 4: Top & bottom products ────────────────────────────────────────
def product_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """Rank all SKUs by net profit to identify top performers and loss-makers."""
    prod = df.groupby(["SKU", "Category"]).agg(
        Revenue    =("Amount",             "sum"),
        Net_Profit =("net_profit",         "sum"),
        Orders     =("Order ID",           "count"),
        Return_Rate=("return_probability", "mean"),
    ).reset_index()
    prod["Net_Margin_Pct"] = prod["Net_Profit"] / prod["Revenue"].replace(0, np.nan) * 100
    return prod.sort_values("Net_Profit", ascending=False).reset_index(drop=True)


def plot_top_bottom_products(prod_df: pd.DataFrame, top_n: int = TOP_N_PRODUCTS) -> None:
    """Side-by-side horizontal bars: top profitable vs top loss-making SKUs."""
    top    = prod_df.head(top_n)
    bottom = prod_df.tail(top_n).sort_values("Net_Profit")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    axes[0].barh(top["SKU"], top["Net_Profit"] / 1_000,
                 color=COLORS["green"], edgecolor="white")
    axes[0].set_title(f"Top {top_n} Profitable Products")
    axes[0].set_xlabel("Net Profit (₹K)")
    axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))

    axes[1].barh(bottom["SKU"], bottom["Net_Profit"] / 1_000,
                 color=COLORS["red"], edgecolor="white")
    axes[1].axvline(0, color="#333333", linewidth=0.8)
    axes[1].set_title(f"Bottom {top_n} Loss-Making Products")
    axes[1].set_xlabel("Net Profit (₹K)")
    axes[1].xaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))

    plt.suptitle("Product Performance Ranking — Top vs Bottom", fontsize=15, fontweight="bold", y=1.01)
    save_chart("15_top_bottom_products.png")


# ── Analysis 5: Return rate vs contribution margin ───────────────────────────
def plot_return_vs_margin(df: pd.DataFrame) -> None:
    """Scatter: categories with high return rate and low margin flagged for action."""
    cat_agg = df.groupby("Category").agg(
        Return_Rate      =("return_probability",  "mean"),
        Avg_Contribution =("contribution_margin", "mean"),
        Net_Profit       =("net_profit",           "sum"),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [COLORS["green"] if p >= 0 else COLORS["red"] for p in cat_agg["Net_Profit"]]
    ax.scatter(cat_agg["Return_Rate"] * 100, cat_agg["Avg_Contribution"],
               c=colors, s=150, edgecolors="white", linewidth=1, zorder=3)

    for _, row in cat_agg.iterrows():
        ax.annotate(row["Category"],
                    (row["Return_Rate"] * 100, row["Avg_Contribution"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=9)

    ax.axhline(cat_agg["Avg_Contribution"].mean(), color=COLORS["gray"],
               linestyle="--", linewidth=1, label="Avg Contribution Margin")
    ax.axvline(cat_agg["Return_Rate"].mean() * 100, color=COLORS["orange"],
               linestyle="--", linewidth=1, label="Avg Return Rate")
    ax.set_xlabel("Return Rate (%)")
    ax.set_ylabel("Avg Contribution Margin (₹)")
    ax.set_title("Return Rate vs Contribution Margin by Category")
    ax.legend()
    save_chart("16_return_vs_margin.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(cat_df: pd.DataFrame, abc_df: pd.DataFrame,
                  vel_df: pd.DataFrame, prod_df: pd.DataFrame) -> None:
    """Save four product summary tables to REPORT_DIR."""
    cat_df.to_csv(REPORT_DIR / "category_performance.csv",         index=False)
    abc_df.to_csv(REPORT_DIR / "abc_analysis.csv",                 index=False)
    vel_df.to_csv(REPORT_DIR / "velocity_analysis.csv",            index=False)
    prod_df.head(50).to_csv(REPORT_DIR / "product_ranking.csv",    index=False)
    log.info("  Saved: category_performance.csv | abc_analysis.csv | velocity_analysis.csv | product_ranking.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(cat_df: pd.DataFrame, abc_df: pd.DataFrame,
                   vel_df: pd.DataFrame, prod_df: pd.DataFrame) -> str:
    """Build product insight text with best/worst comparisons and ABC/velocity findings."""
    best_cat    = cat_df.iloc[0]["Category"]
    worst_cat   = cat_df.iloc[-1]["Category"]
    best_margin = cat_df.iloc[0]["Net_Margin_Pct"]
    worst_margin= cat_df.iloc[-1]["Net_Margin_Pct"]
    margin_gap  = abs(best_margin - worst_margin)

    highest_ret = cat_df.sort_values("Return_Rate", ascending=False).iloc[0]
    a_rev_share = abc_df[abc_df["abc_class"] == "A"]["Revenue_Share"].values[0]
    a_np        = abc_df[abc_df["abc_class"] == "A"]["Net_Profit"].values[0]
    c_np        = abc_df[abc_df["abc_class"] == "C"]["Net_Profit"].values[0]
    slow_np     = (vel_df[vel_df["velocity_class"] == "Slow"]["Net_Profit"].sum()
                   if "Slow" in vel_df["velocity_class"].values else 0)
    loss_count  = (prod_df["Net_Profit"] < 0).sum()

    lines = [
        "=" * 65,
        "  MODULE 3 — PRODUCT ANALYTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  KEY FINDINGS",
        f"  1. Best: '{best_cat}' ({best_margin:.1f}% margin) vs Worst: '{worst_cat}' ({worst_margin:.1f}%)",
        f"     Margin gap: {margin_gap:.1f} percentage points.",
        f"  2. Highest return rate: '{highest_ret['Category']}' at {highest_ret['Return_Rate']*100:.1f}%.",
        f"  3. Class A drives {a_rev_share:.1f}% of revenue. Net Profit: ₹{a_np/1e6:.2f}M.",
        f"  4. Class C contributes ₹{c_np/1e6:.2f}M net profit — mostly a drag.",
        f"  5. {loss_count} SKUs are loss-making — candidates for review/discontinuation.",
        f"  6. Slow-velocity products: ₹{slow_np/1e6:.2f}M net profit — inventory risk.",
        "",
        "  BUSINESS RECOMMENDATIONS",
        f"  R1. PROMOTE '{best_cat}' — {margin_gap:.1f} pp margin advantage over '{worst_cat}'.",
        f"  R2. REVIEW '{worst_cat}' — reprice, bundle, or discontinue loss SKUs.",
        f"  R3. REDUCE returns in '{highest_ret['Category']}' (size guides, better imagery).",
        "  R4. DISCONTINUE Class C SKUs with negative profit — run clearance sales.",
        "  R5. MARKDOWN Slow-velocity products to recover holding costs.",
        "  R6. PROTECT Class A stock levels — stockouts destroy highest-margin revenue.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write product insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "product_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: product_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 3 product analytics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 3 — PRODUCT ANALYTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/5] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 3 — Product Analytics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/5] Category performance ...")
    cat_df = category_performance(df)
    plot_category_performance(cat_df)

    log.info("\n[3/5] ABC & velocity analysis ...")
    abc_df = abc_analysis(df)
    plot_abc_analysis(abc_df)
    vel_df = velocity_analysis(df)
    plot_velocity_analysis(vel_df)

    log.info("\n[4/5] Product ranking & return analysis ...")
    prod_df = product_ranking(df)
    plot_top_bottom_products(prod_df)
    plot_return_vs_margin(df)

    log.info("\n[5/5] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(cat_df, abc_df, vel_df, prod_df)
    text = build_insights(cat_df, abc_df, vel_df, prod_df)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 5")
    log.info("  Tables Generated: 4")
    log.info("-" * 44)


    return {"insights_text": text}


if __name__ == "__main__":
    run()
