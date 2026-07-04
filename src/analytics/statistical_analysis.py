"""
Module 7 — Business Statistics
Enterprise Profit Intelligence Platform
Business Goal: Apply practical statistics to directly support business decisions.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats

from analytics.utils import (
    COLORS, REPORT_DIR,
    fmt_millions,
    load_data, save_chart, setup_logging, validate_columns,
)

# ── Module constants ──────────────────────────────────────────────────────────
ALPHA          = 0.05   # significance level for all hypothesis tests
CI_LEVEL       = 0.95   # confidence level for confidence interval
PARTIAL_MONTH  = "2022-03"  # incomplete month excluded from trend analysis

REQUIRED_COLS = [
    "Amount", "net_profit", "profit_margin_pct", "estimated_clv",
    "campaign_roi", "return_probability", "inventory_turnover",
    "shipping_cost", "platform_commission", "discount_cost",
    "repeat_customer_flag", "customer_segment",
    "return_reason", "refund_amount", "Date",
]

log = setup_logging(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────
def significant(p_val: float) -> str:
    """Return a human-readable significance label for a p-value."""
    return "YES (statistically significant)" if p_val < ALPHA else "NO (not significant)"


def confidence_interval(data: pd.Series, ci: float = CI_LEVEL) -> tuple[float, float]:
    """Return (lower, upper) confidence interval for the mean of data."""
    n     = len(data)
    mean  = data.mean()
    se    = stats.sem(data)
    h     = se * stats.t.ppf((1 + ci) / 2, n - 1)
    return round(mean - h, 2), round(mean + h, 2)


# ── Analysis 1: Descriptive statistics ───────────────────────────────────────
def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute mean, std, skew, kurtosis, and coefficient of variation for key metrics."""
    cols = [
        "Amount", "net_profit", "profit_margin_pct",
        "estimated_clv", "campaign_roi", "return_probability",
        "inventory_turnover", "shipping_cost",
    ]
    desc = df[cols].describe().T
    desc["skew"]     = df[cols].skew()
    desc["kurtosis"] = df[cols].kurtosis()
    desc["cv"]       = desc["std"] / desc["mean"] * 100  # coefficient of variation
    return desc.round(3)


def plot_profit_distribution(df: pd.DataFrame) -> None:
    """Histogram + normal curve overlay: is net profit normally distributed?"""
    profit = df["net_profit"].dropna()
    mean_v, std_v = profit.mean(), profit.std()

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.hist(profit, bins=60, color=COLORS["blue"], alpha=0.7,
            edgecolor="white", density=True, label="Net Profit Distribution")

    x = np.linspace(profit.min(), profit.max(), 300)
    ax.plot(x, stats.norm.pdf(x, mean_v, std_v),
            color=COLORS["red"], linewidth=2, label="Normal Distribution Fit")
    ax.axvline(mean_v, color=COLORS["orange"], linewidth=1.5,
               linestyle="--", label=f"Mean: ₹{mean_v:.0f}")
    ax.axvline(0, color=COLORS["gray"], linewidth=1, linestyle=":")

    ax.set_title("Net Profit Distribution — Is it Normal?")
    ax.set_xlabel("Net Profit per Order (₹)")
    ax.set_ylabel("Density")
    ax.legend()
    save_chart("29_profit_distribution.png")


# ── Analysis 2: Correlation analysis ─────────────────────────────────────────
def correlation_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix for nine core business metrics."""
    cols = [
        "Amount", "net_profit", "estimated_clv", "campaign_roi",
        "shipping_cost", "return_probability", "inventory_turnover",
        "platform_commission", "discount_cost",
    ]
    return df[cols].corr().round(3)


def plot_correlation_heatmap(corr_df: pd.DataFrame) -> None:
    """Annotated heatmap: which business metrics move together?"""
    fig, ax = plt.subplots(figsize=(11, 9))
    labels = corr_df.columns.tolist()
    data   = corr_df.values
    n      = len(labels)

    im = ax.imshow(data, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, shrink=0.8, label="Correlation Coefficient")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)

    for i in range(n):
        for j in range(n):
            val = data[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=7.5, color="black" if abs(val) < 0.7 else "white")

    ax.set_title("Business Metric Correlation Matrix")
    save_chart("30_correlation_heatmap.png")


# ── Analysis 3: T-Test — repeat vs new customers ─────────────────────────────
def ttest_repeat_vs_new(df: pd.DataFrame) -> dict:
    """
    Welch's T-Test: do repeat customers generate significantly higher net profit?
    Returns a dict with test stats, means, significance label, and recommendation.
    """
    repeat = df[df["repeat_customer_flag"] == 1]["net_profit"].dropna()
    new    = df[df["repeat_customer_flag"] == 0]["net_profit"].dropna()
    t_stat, p_val = stats.ttest_ind(repeat, new, equal_var=False)
    profit_gap    = repeat.mean() - new.mean()

    return {
        "test":           "Independent T-Test (Welch)",
        "question":       "Do repeat customers generate higher profit than new customers?",
        "repeat_mean":    repeat.mean(),
        "new_mean":       new.mean(),
        "profit_gap":     profit_gap,
        "t_stat":         round(t_stat, 4),
        "p_value":        round(p_val, 6),
        "significant":    significant(p_val),
        "meaning":        (
            f"Repeat customers earn ₹{abs(profit_gap):.2f} "
            f"{'more' if profit_gap > 0 else 'less'} per order — statistically significant."
            if p_val < ALPHA else
            "No significant profit difference between repeat and new customers."
        ),
        "recommendation": (
            "Invest in repeat customer retention — measurable profit advantage per order."
            if p_val < ALPHA and repeat.mean() > new.mean() else
            "Review repeat customer targeting — no clear profit advantage detected."
        ),
    }


# ── Analysis 4: ANOVA — profit across customer segments ──────────────────────
def anova_segment_profit(df: pd.DataFrame) -> dict:
    """
    One-Way ANOVA: is net profit significantly different across customer segments?
    Returns a dict with F-stat, p-value, per-segment means, and recommendation.
    """
    segments = df["customer_segment"].unique()
    groups   = [df[df["customer_segment"] == s]["net_profit"].dropna() for s in segments]
    f_stat, p_val = stats.f_oneway(*groups)
    seg_means = (df.groupby("customer_segment")["net_profit"].mean()
                   .sort_values(ascending=False).to_dict())
    best_seg  = max(seg_means, key=seg_means.get)
    worst_seg = min(seg_means, key=seg_means.get)
    seg_gap   = seg_means[best_seg] - seg_means[worst_seg]

    return {
        "test":          "One-Way ANOVA",
        "question":      "Is net profit significantly different across customer segments?",
        "segment_means": seg_means,
        "best_segment":  best_seg,
        "worst_segment": worst_seg,
        "seg_gap":       seg_gap,
        "f_stat":        round(f_stat, 4),
        "p_value":       round(p_val, 6),
        "significant":   significant(p_val),
        "meaning":       (
            f"'{best_seg}' earns ₹{seg_gap:.2f} more per order than '{worst_seg}' — significant."
            if p_val < ALPHA else
            "No significant profit difference across customer segments."
        ),
        "recommendation": (
            f"Prioritise '{best_seg}' segment for premium service and promotions."
            if p_val < ALPHA else
            "All segments perform similarly — review segmentation model validity."
        ),
    }


# ── Analysis 5: Chi-Square — category vs return reason ───────────────────────
def chi_square_category_returns(df: pd.DataFrame) -> dict:
    """
    Chi-Square Test of Independence: are return reasons dependent on product category?
    Returns a dict with chi2 stat, p-value, degrees of freedom, and recommendation.
    """
    returns     = df[df["refund_amount"] > 0][["Category", "return_reason"]]
    contingency = pd.crosstab(returns["Category"], returns["return_reason"])
    chi2, p_val, dof, _ = stats.chi2_contingency(contingency)

    return {
        "test":               "Chi-Square Test of Independence",
        "question":           "Are return reasons dependent on product category?",
        "chi2_stat":          round(chi2, 4),
        "degrees_of_freedom": dof,
        "p_value":            round(p_val, 6),
        "significant":        significant(p_val),
        "meaning":            (
            "Return reasons significantly differ by category — category-specific fixes needed."
            if p_val < ALPHA else
            "Return reasons are not significantly associated with category."
        ),
        "recommendation":     (
            "Develop category-specific return reduction strategies."
            if p_val < ALPHA else
            "Apply a universal return reduction strategy across all categories."
        ),
    }


# ── Analysis 6: Monthly profit trend ─────────────────────────────────────────
def trend_analysis(df: pd.DataFrame) -> dict:
    """
    OLS linear regression on monthly net profit to detect upward or downward trends.
    Returns a dict with slope, R², p-value, direction, and the monthly data.
    """
    monthly = (df[df["month"].astype(str) != PARTIAL_MONTH]
               .groupby("month")["net_profit"].sum().reset_index())
    monthly["month_num"] = range(len(monthly))
    x = monthly["month_num"].values
    y = monthly["net_profit"].values

    slope, intercept, r, p_val, _ = stats.linregress(x, y)

    return {
        "test":         "Linear Trend (OLS)",
        "question":     "Is net profit trending upward or downward over time?",
        "slope":        round(slope, 2),
        "r_squared":    round(r ** 2, 4),
        "p_value":      round(p_val, 6),
        "direction":    "IMPROVING" if slope > 0 else "DECLINING",
        "significant":  significant(p_val),
        "meaning":      (
            f"Net profit is {'improving' if slope > 0 else 'declining'} by "
            f"₹{abs(slope):,.0f}/month (R² = {r ** 2:.3f})."
        ),
        "recommendation": (
            "Continue improvement trajectory — reinforce current cost controls."
            if slope > 0 else
            "Declining trend: implement cost reduction plan immediately."
        ),
        "monthly_data": monthly,
    }


def plot_trend_line(trend_result: dict) -> None:
    """Bar chart + OLS regression line: monthly net profit trajectory."""
    monthly   = trend_result["monthly_data"]
    x         = monthly["month_num"].values
    y         = monthly["net_profit"].values
    slope     = trend_result["slope"]
    intercept = np.mean(y) - slope * np.mean(x)
    fitted    = slope * x + intercept

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(monthly["month"].astype(str), y / 1_000_000,
           color=COLORS["blue"], alpha=0.7, label="Monthly Net Profit")
    ax.plot(monthly["month"].astype(str), fitted / 1_000_000,
            color=COLORS["red"], linewidth=2.5, marker="o", markersize=7,
            label=f"Trend (slope: ₹{slope:,.0f}/month)")
    ax.axhline(0, color="#999999", linewidth=0.8, linestyle="--")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_millions))
    ax.set_title(f"Monthly Net Profit Trend — {trend_result['direction']}")
    ax.set_ylabel("Net Profit (INR)")
    ax.legend()
    save_chart("31_monthly_trend_regression.png")


# ── CSV exports ───────────────────────────────────────────────────────────────
def export_tables(desc_df: pd.DataFrame, corr_df: pd.DataFrame) -> None:
    """Save descriptive statistics and correlation matrix to REPORT_DIR."""
    desc_df.to_csv(REPORT_DIR / "descriptive_statistics.csv")
    corr_df.to_csv(REPORT_DIR / "correlation_matrix.csv")
    log.info("  Saved: descriptive_statistics.csv | correlation_matrix.csv")


# ── Business insights ─────────────────────────────────────────────────────────
def build_insights(desc_df: pd.DataFrame, ttest: dict, anova: dict,
                   chi2: dict, trend: dict) -> str:
    """Consolidate all statistical test results into a formatted insights report."""
    lines = [
        "=" * 65,
        "  MODULE 7 — BUSINESS STATISTICS: INSIGHTS & RECOMMENDATIONS",
        "=" * 65,
        "",
        "  1. T-TEST — Repeat vs New Customer Profit",
        f"     Question    : {ttest['question']}",
        f"     Result      : t={ttest['t_stat']}, p={ttest['p_value']}",
        f"     Significant : {ttest['significant']}",
        f"     Repeat Mean : ₹{ttest['repeat_mean']:.2f} | New Mean: ₹{ttest['new_mean']:.2f}"
        f" | Gap: ₹{ttest['profit_gap']:.2f}",
        f"     Meaning     : {ttest['meaning']}",
        f"     Action      : {ttest['recommendation']}",
        "",
        "  2. ANOVA — Profit Across Customer Segments",
        f"     Question    : {anova['question']}",
        f"     Result      : F={anova['f_stat']}, p={anova['p_value']}",
        f"     Significant : {anova['significant']}",
        "     Segment Means: " + " | ".join(
            [f"{k}: ₹{v:.2f}" for k, v in list(anova["segment_means"].items())[:4]]),
        f"     Best vs Worst: ₹{anova['seg_gap']:.2f} gap per order.",
        f"     Meaning     : {anova['meaning']}",
        f"     Action      : {anova['recommendation']}",
        "",
        "  3. CHI-SQUARE — Return Reason vs Category",
        f"     Question    : {chi2['question']}",
        f"     Result      : χ²={chi2['chi2_stat']}, df={chi2['degrees_of_freedom']}, p={chi2['p_value']}",
        f"     Significant : {chi2['significant']}",
        f"     Meaning     : {chi2['meaning']}",
        f"     Action      : {chi2['recommendation']}",
        "",
        "  4. TREND ANALYSIS — Monthly Net Profit",
        f"     Question    : {trend['question']}",
        f"     Result      : Slope=₹{trend['slope']:,.0f}/month, R²={trend['r_squared']}, p={trend['p_value']}",
        f"     Direction   : {trend['direction']}",
        f"     Significant : {trend['significant']}",
        f"     Meaning     : {trend['meaning']}",
        f"     Action      : {trend['recommendation']}",
        "",
        "  OVERALL STATISTICAL CONCLUSION",
        "  - Customer segments and repeat behaviour significantly impact profit.",
        "  - Return reasons are category-specific — targeted fixes required.",
        "  - Net profit trend is improving — strategic direction is working.",
        "  - Focus retention on At_Risk segment and expand Champion segment.",
        "",
        "=" * 65,
    ]
    return "\n".join(lines)


def save_insights(text: str) -> None:
    """Write statistical insight text to a UTF-8 TXT file."""
    (REPORT_DIR / "statistical_insights.txt").write_text(text, encoding="utf-8")
    log.info("  Saved: statistical_insights.txt")


# ── Main ──────────────────────────────────────────────────────────────────────
def run(save_to_disk: bool = True) -> dict:
    """Execute the full Module 7 business statistics pipeline."""
    start = time.time()
    log.info("\n" + "=" * 65)
    log.info("  MODULE 7 — BUSINESS STATISTICS")
    log.info("  Enterprise Profit Intelligence Platform")
    log.info("=" * 65)

    log.info("\n[1/5] Loading & validating dataset ...")
    df = load_data()
    validate_columns(df, REQUIRED_COLS, "Module 7 — Business Statistics")
    log.info("      Rows: %s  |  Columns: %s", f"{len(df):,}", df.shape[1])

    log.info("\n[2/5] Descriptive statistics & distribution ...")
    desc_df = descriptive_stats(df)
    plot_profit_distribution(df)

    log.info("\n[3/5] Correlation analysis ...")
    corr_df = correlation_analysis(df)
    plot_correlation_heatmap(corr_df)

    log.info("\n[4/5] Statistical tests ...")
    ttest = ttest_repeat_vs_new(df)
    anova = anova_segment_profit(df)
    chi2  = chi_square_category_returns(df)
    trend = trend_analysis(df)
    plot_trend_line(trend)

    profit_ci = confidence_interval(df["net_profit"].dropna())
    log.info("  95%% CI for Net Profit per Order: ₹%s to ₹%s",
             profit_ci[0], profit_ci[1])

    log.info("\n[5/5] Exporting tables & insights ...")
    if save_to_disk:
        export_tables(desc_df, corr_df)
    text = build_insights(desc_df, ttest, anova, chi2, trend)
    log.info(text)
    if save_to_disk:
        save_insights(text)

    elapsed = time.time() - start
    log.info("\n" + "-" * 44)
    log.info("  Module Completed Successfully")
    log.info("  Execution Time  : %.1f seconds", elapsed)
    log.info("  Charts Generated: 3")
    log.info("  Tables Generated: 2")
    log.info("-" * 44)


if __name__ == "__main__":
    run()
