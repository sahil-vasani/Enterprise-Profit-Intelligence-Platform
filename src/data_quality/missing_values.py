"""
missing_values.py – Missing Values Analysis Module.
Analyses every column for missing values, classifies dtypes, and assigns remediation recommendations.
Output: reports/data_quality/missing_values_report.csv
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATASET_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
REPORT_DIR: Path = PROJECT_ROOT / "reports" / "data_quality"
REPORT_PATH: Path = REPORT_DIR / "missing_values_report.csv"

THRESHOLD_REMOVE: float = 80.0
THRESHOLD_INVESTIGATE: float = 50.0

CRITICAL_COLUMNS: set = {"Order ID", "Date", "SKU", "customer_id", "Amount", "Qty", "Status"}

MEAN_IMPUTE_COLUMNS: set = {
    "estimated_shipping_distance", "fuel_surcharge", "shipping_insurance",
    "estimated_clv", "estimated_cac", "loyalty_score", "campaign_roi",
    "attributed_revenue", "contribution_margin", "product_profitability_score",
}

MEDIAN_IMPUTE_COLUMNS: set = {
    "shipping_cost", "cogs", "gross_profit", "net_profit", "profit_margin_pct",
    "inventory_available", "inventory_age_days", "inventory_turnover", "refund_amount",
    "refurbishment_cost", "disposal_cost", "safety_stock", "reorder_point",
    "reorder_quantity", "delay_probability", "return_probability", "stockout_probability",
    "discount_cost", "marketing_attribution_cost", "campaign_cost", "platform_commission",
    "payment_gateway_fee", "reverse_logistics_cost", "cancellation_cost", "packaging_cost",
    "warehouse_handling_cost", "inventory_holding_cost", "profit_leakage",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_quality.missing_values")


def ensure_report_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    logger.info("Loading dataset from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Dataset loaded – rows: %d, columns: %d", *df.shape)
    return df


def classify_dtype(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series): return "Boolean"
    if pd.api.types.is_numeric_dtype(series): return "Numeric"
    if pd.api.types.is_datetime64_any_dtype(series): return "DateTime"
    if series.dtype == object:
        try:
            pd.to_datetime(series.dropna().head(50), format="mixed")
            return "DateTime"
        except (ValueError, TypeError):
            pass
        return "Categorical"
    return "Unknown"


def build_recommendation(col: str, dtype_label: str, missing_pct: float) -> str:
    """Priority: no missing -> Keep; critical col -> Investigate; high missing -> Remove/Investigate;
    numeric -> Impute Mean/Median; else -> Keep."""
    if missing_pct == 0.0: return "Keep"
    if col in CRITICAL_COLUMNS: return "Investigate"
    if missing_pct >= THRESHOLD_REMOVE: return "Remove"
    if missing_pct >= THRESHOLD_INVESTIGATE: return "Investigate"
    if dtype_label == "Numeric":
        return "Impute Mean" if col in MEAN_IMPUTE_COLUMNS else "Impute Median"
    return "Keep"


def analyse_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    total_rows = len(df)
    logger.info("Analysing missing values across %d columns ...", df.shape[1])
    records = []
    for col in df.columns:
        series = df[col]
        missing_count = int(series.isnull().sum())
        missing_pct = round((missing_count / total_rows) * 100, 4) if total_rows > 0 else 0.0
        dtype_label = classify_dtype(series)
        records.append({
            "Column Name": col,
            "Data Type": dtype_label,
            "Missing Count": missing_count,
            "Missing Percentage": missing_pct,
            "Recommendation": build_recommendation(col, dtype_label, missing_pct),
        })
    report_df = pd.DataFrame(records).sort_values(
        by=["Missing Count", "Column Name"], ascending=[False, True]
    ).reset_index(drop=True)
    logger.info(
        "Analysis complete – %d of %d columns have missing values.",
        int((report_df["Missing Count"] > 0).sum()), len(report_df),
    )
    return report_df


def save_report(report_df: pd.DataFrame, output_path: Path) -> None:
    report_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Report saved -> %s", output_path)


def print_summary(report_df: pd.DataFrame) -> None:
    total_cols = len(report_df)
    cols_with_missing = int((report_df["Missing Count"] > 0).sum())
    print("\n" + "=" * 65)
    print("  MISSING VALUES REPORT – SUMMARY")
    print("=" * 65)
    print(f"  Total columns analysed  : {total_cols}")
    print(f"  Columns with missing    : {cols_with_missing}")
    print(f"  Columns fully present   : {total_cols - cols_with_missing}")
    print("\n  Recommendation breakdown:")
    for rec, count in report_df["Recommendation"].value_counts().items():
        print(f"    {rec:<20}  {count:>4} columns")
    top_missing = report_df[report_df["Missing Count"] > 0].head(10)
    if not top_missing.empty:
        print("\n  Top columns by missing %:")
        for _, row in top_missing.iterrows():
            print(f"    {row['Column Name']:<42}  {row['Missing Percentage']:>7.2f}%  ->  {row['Recommendation']}")
    print("=" * 65 + "\n")


def run(dataset_path: Optional[Path] = None, report_path: Optional[Path] = None) -> pd.DataFrame:
    _dataset = dataset_path or DATASET_PATH
    _report = report_path or REPORT_PATH
    ensure_report_dir(_report.parent)
    df = load_dataset(_dataset)
    report_df = analyse_missing_values(df)
    save_report(report_df, _report)
    print_summary(report_df)
    return report_df


if __name__ == "__main__":
    try:
        run()
    except FileNotFoundError as exc:
        logger.error("Dataset not found: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during missing-value analysis: %s", exc)
        sys.exit(2)