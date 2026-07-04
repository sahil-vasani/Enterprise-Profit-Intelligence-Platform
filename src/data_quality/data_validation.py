"""
data_validation.py – Business Rule Validation Module.
Validates each row against domain-specific business rules.
Output: reports/data_quality/validation_report.csv
"""

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATASET_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
REPORT_DIR: Path = PROJECT_ROOT / "reports" / "data_quality"
REPORT_PATH: Path = REPORT_DIR / "validation_report.csv"

MAX_SAMPLE_VALUES: int = 5
FLOAT_TOLERANCE: float = 0.01
STATUS_PASS, STATUS_FAIL, STATUS_SKIP = "PASS", "FAIL", "SKIP"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_quality.data_validation")


def ensure_report_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    logger.info("Loading dataset from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Dataset loaded – rows: %d, columns: %d", *df.shape)
    return df


def format_sample_values(series: pd.Series, max_count: int = MAX_SAMPLE_VALUES) -> str:
    samples = series.dropna().head(max_count).tolist()
    return " | ".join(str(v) for v in samples) if samples else "N/A"


def evaluate_rule(
    rule_name: str,
    df: pd.DataFrame,
    required_cols: list,
    condition_fn: Callable[[pd.DataFrame], pd.Series],
    sample_col: str,
) -> dict:
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        logger.warning("Rule '%s' skipped – missing column(s): %s", rule_name, missing_cols)
        return {
            "Rule": rule_name, "Status": STATUS_SKIP, "Failed Rows": 0,
            "Sample Values": f"Skipped – column(s) absent: {', '.join(missing_cols)}",
        }

    try:
        violation_mask = condition_fn(df).fillna(False).astype(bool)
    except Exception as exc:
        logger.error("Rule '%s' evaluation error: %s", rule_name, exc)
        return {"Rule": rule_name, "Status": STATUS_FAIL, "Failed Rows": -1,
                "Sample Values": f"Evaluation error: {exc}"}

    failed_rows = int(violation_mask.sum())
    status = STATUS_PASS if failed_rows == 0 else STATUS_FAIL
    sample_values = (
        format_sample_values(df.loc[violation_mask, sample_col])
        if failed_rows > 0 and sample_col in df.columns else "None"
    )
    logger.info("Rule: %-55s  Status: %-4s  Failed: %d", rule_name, status, failed_rows)
    return {"Rule": rule_name, "Status": status, "Failed Rows": failed_rows, "Sample Values": sample_values}


def define_rules() -> list:
    return [
        {
            "rule_name": "Qty > 0",
            "required_cols": ["Qty"],
            "condition_fn": lambda df: pd.to_numeric(df["Qty"], errors="coerce") <= 0,
            "sample_col": "Qty",
        },
        {
            "rule_name": "Amount >= 0",
            "required_cols": ["Amount"],
            "condition_fn": lambda df: pd.to_numeric(df["Amount"], errors="coerce") < 0,
            "sample_col": "Amount",
        },
        {
            "rule_name": "shipping_cost >= 0",
            "required_cols": ["shipping_cost"],
            "condition_fn": lambda df: pd.to_numeric(df["shipping_cost"], errors="coerce") < 0,
            "sample_col": "shipping_cost",
        },
        {
            "rule_name": "cogs <= Amount",
            "required_cols": ["cogs", "Amount"],
            "condition_fn": lambda df: (
                pd.to_numeric(df["cogs"], errors="coerce") > pd.to_numeric(df["Amount"], errors="coerce")
            ),
            "sample_col": "cogs",
        },
        {
            "rule_name": "profit_margin_pct between -100 and 100",
            "required_cols": ["profit_margin_pct"],
            "condition_fn": lambda df: (
                (pd.to_numeric(df["profit_margin_pct"], errors="coerce") < -100)
                | (pd.to_numeric(df["profit_margin_pct"], errors="coerce") > 100)
            ),
            "sample_col": "profit_margin_pct",
        },
        {
            "rule_name": "return_probability between 0 and 1",
            "required_cols": ["return_probability"],
            "condition_fn": lambda df: (
                (pd.to_numeric(df["return_probability"], errors="coerce") < 0)
                | (pd.to_numeric(df["return_probability"], errors="coerce") > 1)
            ),
            "sample_col": "return_probability",
        },
        {
            "rule_name": "inventory_available >= 0",
            "required_cols": ["inventory_available"],
            "condition_fn": lambda df: pd.to_numeric(df["inventory_available"], errors="coerce") < 0,
            "sample_col": "inventory_available",
        },
        {
            "rule_name": "customer_id not null",
            "required_cols": ["customer_id"],
            "condition_fn": lambda df: df["customer_id"].isnull(),
            "sample_col": "customer_id",
        },
        {
            "rule_name": f"gross_profit ~= Amount - cogs (tol={FLOAT_TOLERANCE})",
            "required_cols": ["gross_profit", "Amount", "cogs"],
            "condition_fn": lambda df: (
                (
                    pd.to_numeric(df["gross_profit"], errors="coerce")
                    - (pd.to_numeric(df["Amount"], errors="coerce") - pd.to_numeric(df["cogs"], errors="coerce"))
                ).abs() > FLOAT_TOLERANCE
            ),
            "sample_col": "gross_profit",
        },
        {
            "rule_name": "net_profit <= gross_profit",
            "required_cols": ["net_profit", "gross_profit"],
            "condition_fn": lambda df: (
                pd.to_numeric(df["net_profit"], errors="coerce") > pd.to_numeric(df["gross_profit"], errors="coerce")
            ),
            "sample_col": "net_profit",
        },
        {
            "rule_name": "delay_probability between 0 and 1",
            "required_cols": ["delay_probability"],
            "condition_fn": lambda df: (
                (pd.to_numeric(df["delay_probability"], errors="coerce") < 0)
                | (pd.to_numeric(df["delay_probability"], errors="coerce") > 1)
            ),
            "sample_col": "delay_probability",
        },
        {
            "rule_name": "stockout_probability between 0 and 1",
            "required_cols": ["stockout_probability"],
            "condition_fn": lambda df: (
                (pd.to_numeric(df["stockout_probability"], errors="coerce") < 0)
                | (pd.to_numeric(df["stockout_probability"], errors="coerce") > 1)
            ),
            "sample_col": "stockout_probability",
        },
        {
            "rule_name": "loyalty_score between 0 and 100",
            "required_cols": ["loyalty_score"],
            "condition_fn": lambda df: (
                (pd.to_numeric(df["loyalty_score"], errors="coerce") < 0)
                | (pd.to_numeric(df["loyalty_score"], errors="coerce") > 100)
            ),
            "sample_col": "loyalty_score",
        },
        {
            "rule_name": "campaign_roi >= -100",
            "required_cols": ["campaign_roi"],
            "condition_fn": lambda df: pd.to_numeric(df["campaign_roi"], errors="coerce") < -100,
            "sample_col": "campaign_roi",
        },
        {
            "rule_name": "Order ID not null",
            "required_cols": ["Order ID"],
            "condition_fn": lambda df: df["Order ID"].isnull(),
            "sample_col": "Order ID",
        },
    ]


def build_validation_report(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Evaluating business rules ...") 
    records = [
    evaluate_rule(df=df, **rule)
    for rule in define_rules()
    ]   
    report_df = pd.DataFrame(records)
    logger.info(
        "Validation complete – %d rules: %d PASS, %d FAIL, %d SKIP.",
        len(report_df),
        (report_df["Status"] == STATUS_PASS).sum(),
        (report_df["Status"] == STATUS_FAIL).sum(),
        (report_df["Status"] == STATUS_SKIP).sum(),
    )
    return report_df


def save_report(report_df: pd.DataFrame, output_path: Path) -> None:
    report_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Report saved -> %s", output_path)


def print_summary(report_df: pd.DataFrame) -> None:
    total = len(report_df)
    passes = (report_df["Status"] == STATUS_PASS).sum()
    fails = (report_df["Status"] == STATUS_FAIL).sum()
    skips = (report_df["Status"] == STATUS_SKIP).sum()

    print("\n" + "=" * 80)
    print("  DATA VALIDATION REPORT – SUMMARY")
    print("=" * 80)
    print(f"  Total rules evaluated : {total}")
    print(f"  PASS                  : {passes}")
    print(f"  FAIL                  : {fails}")
    print(f"  SKIP (col absent)     : {skips}")
    print(f"\n  {'Rule':<52} {'Status':<6} {'Failed Rows':>12}")
    print("  " + "-" * 72)
    for _, row in report_df.iterrows():
        icon = {"PASS": "[OK]", "FAIL": "[!!]", "SKIP": "[--]"}.get(row["Status"], "   ")
        print(f"  {icon} {str(row['Rule']):<50} {row['Status']:<6} {row['Failed Rows']:>12,}")
    print("=" * 80 + "\n")


def run(dataset_path: Optional[Path] = None, report_path: Optional[Path] = None) -> pd.DataFrame:
    _dataset = dataset_path or DATASET_PATH
    _report = report_path or REPORT_PATH
    ensure_report_dir(_report.parent)
    df = load_dataset(_dataset)
    report_df = build_validation_report(df)
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
        logger.exception("Unexpected error during data validation: %s", exc)
        sys.exit(2)