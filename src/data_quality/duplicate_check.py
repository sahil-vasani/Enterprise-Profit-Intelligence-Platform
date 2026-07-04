"""
duplicate_check.py – Duplicate Detection Module.
Detects: duplicate Order IDs, fully duplicate rows, duplicate SKUs, duplicate Customer IDs.
Output: reports/data_quality/duplicate_report.csv
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATASET_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
REPORT_DIR: Path = PROJECT_ROOT / "reports" / "data_quality"
REPORT_PATH: Path = REPORT_DIR / "duplicate_report.csv"

MAX_SAMPLE_VALUES: int = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_quality.duplicate_check")


def ensure_report_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    logger.info("Loading dataset from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Dataset loaded – rows: %d, columns: %d", *df.shape)
    return df


def format_samples(values: pd.Index, max_count: int = MAX_SAMPLE_VALUES) -> str:
    return " | ".join(str(v) for v in list(values[:max_count]))


def check_duplicate_order_ids(df: pd.DataFrame) -> dict:
    col = "Order ID"
    if col not in df.columns:
        return {"Duplicate Type": "Duplicate Order IDs", "Count": 0, "Sample Values": "N/A – column not present"}
    mask = df[col].duplicated(keep=False)
    dup_values = df.loc[mask, col].dropna().unique()
    count = int(mask.sum())
    logger.info("Duplicate Order IDs: %d rows (%d unique IDs)", count, len(dup_values))
    return {"Duplicate Type": "Duplicate Order IDs", "Count": count,
            "Sample Values": format_samples(dup_values) if count > 0 else "None"}


def check_duplicate_rows(df: pd.DataFrame) -> dict:
    compare_cols = [c for c in df.columns if c.lower() != "index"]
    mask = df[compare_cols].duplicated(keep=False)
    count = int(mask.sum())
    sample_indices = df.index[mask][:MAX_SAMPLE_VALUES].tolist()
    sample_str = " | ".join(f"Row {i}" for i in sample_indices) if count > 0 else "None"
    logger.info("Fully duplicate rows: %d", count)
    return {"Duplicate Type": "Duplicate Rows (All Columns)", "Count": count, "Sample Values": sample_str}


def check_duplicate_skus(df: pd.DataFrame) -> dict:
    col = "SKU"
    if col not in df.columns:
        return {"Duplicate Type": "Duplicate SKUs", "Count": 0, "Sample Values": "N/A – column not present"}
    repeated = df[col].value_counts()
    repeated = repeated[repeated > 1]
    logger.info("Duplicate SKUs: %d unique SKUs (%d total rows)", len(repeated), int(repeated.sum()))
    return {"Duplicate Type": "Duplicate SKUs", "Count": len(repeated),
            "Sample Values": format_samples(repeated.index) if len(repeated) > 0 else "None"}


def check_duplicate_customer_ids(df: pd.DataFrame) -> dict:
    col = "customer_id"
    if col not in df.columns:
        return {"Duplicate Type": "Duplicate Customer IDs", "Count": 0, "Sample Values": "N/A – column not present"}
    repeated = df[col].value_counts()
    repeated = repeated[repeated > 1]
    logger.info("Duplicate Customer IDs: %d unique customers (%d total rows)", len(repeated), int(repeated.sum()))
    return {"Duplicate Type": "Duplicate Customer IDs", "Count": len(repeated),
            "Sample Values": format_samples(repeated.index) if len(repeated) > 0 else "None"}


def build_duplicate_report(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Running duplicate checks ...")
    checks = [
        check_duplicate_order_ids(df),
        check_duplicate_rows(df),
        check_duplicate_skus(df),
        check_duplicate_customer_ids(df),
    ]
    return pd.DataFrame(checks)


def save_report(report_df: pd.DataFrame, output_path: Path) -> None:
    report_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Report saved -> %s", output_path)


def print_summary(report_df: pd.DataFrame, total_rows: int) -> None:
    print("\n" + "=" * 65)
    print("  DUPLICATE CHECK REPORT – SUMMARY")
    print("=" * 65)
    print(f"  Source dataset total rows : {total_rows:,}\n")
    for _, row in report_df.iterrows():
        status = "FOUND" if row["Count"] > 0 else "CLEAN"
        print(f"  [{status}]  {row['Duplicate Type']:<38}  Count: {row['Count']:>6,}")
        if row["Count"] > 0:
            display = row["Sample Values"]
            print(f"           Samples: {display[:77] + '...' if len(display) > 80 else display}")
    print("=" * 65 + "\n")


def run(dataset_path: Optional[Path] = None, report_path: Optional[Path] = None) -> pd.DataFrame:
    _dataset = dataset_path or DATASET_PATH
    _report = report_path or REPORT_PATH
    ensure_report_dir(_report.parent)
    df = load_dataset(_dataset)
    report_df = build_duplicate_report(df)
    save_report(report_df, _report)
    print_summary(report_df, total_rows=len(df))
    return report_df


if __name__ == "__main__":
    try:
        run()
    except FileNotFoundError as exc:
        logger.error("Dataset not found: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during duplicate check: %s", exc)
        sys.exit(2)