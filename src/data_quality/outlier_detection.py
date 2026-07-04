"""
outlier_detection.py – Outlier Detection Module.
Detects statistical outliers using IQR and Z-score methods on key numeric columns.
Output: reports/data_quality/outlier_report.csv
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATASET_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
REPORT_DIR: Path = PROJECT_ROOT / "reports" / "data_quality"
REPORT_PATH: Path = REPORT_DIR / "outlier_report.csv"

TARGET_COLUMNS: list = [
    "Amount", "shipping_cost", "cogs", "gross_profit",
    "net_profit", "profit_margin_pct", "inventory_available",
]
IQR_MULTIPLIER: float = 1.5
ZSCORE_THRESHOLD: float = 3.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_quality.outlier_detection")


def ensure_report_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_dataset(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    logger.info("Loading dataset from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Dataset loaded – rows: %d, columns: %d", *df.shape)
    return df


def detect_iqr_outliers(series: pd.Series, multiplier: float = IQR_MULTIPLIER) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    mask = (series < (q1 - multiplier * iqr)) | (series > (q3 + multiplier * iqr))
    return mask & series.notna()


def detect_zscore_outliers(series: pd.Series, threshold: float = ZSCORE_THRESHOLD) -> pd.Series:
    valid = series.dropna()
    if valid.std() == 0:
        return pd.Series(False, index=series.index)
    z_scores = pd.Series(np.nan, index=series.index)
    z_scores.loc[valid.index] = np.abs(stats.zscore(valid, ddof=0))
    return z_scores > threshold


def analyse_column_outliers(col: str, series: pd.Series, total_rows: int) -> list:
    records = []
    for method, mask in [("IQR", detect_iqr_outliers(series)), ("Z-score", detect_zscore_outliers(series))]:
        outlier_count = int(mask.sum())
        outlier_pct = round((outlier_count / total_rows) * 100, 4) if total_rows > 0 else 0.0
        records.append({"Column": col, "Method": method, "Outlier Count": outlier_count, "Percentage": outlier_pct})
    return records


def build_outlier_report(df: pd.DataFrame, target_columns: list) -> pd.DataFrame:
    total_rows = len(df)
    logger.info("Running outlier detection on %d columns ...", len(target_columns))
    records = []
    for col in target_columns:
        if col not in df.columns:
            logger.warning("Column '%s' not found – skipping.", col)
            records += [{"Column": col, "Method": m, "Outlier Count": 0, "Percentage": 0.0} for m in ["IQR", "Z-score"]]
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() == 0:
            logger.warning("Column '%s' has no non-null numeric values – skipping.", col)
            records += [{"Column": col, "Method": m, "Outlier Count": 0, "Percentage": 0.0} for m in ["IQR", "Z-score"]]
            continue
        logger.info("Analysing column: %s (non-null rows: %d)", col, series.notna().sum())
        records.extend(analyse_column_outliers(col, series, total_rows))
    return pd.DataFrame(records)


def save_report(report_df: pd.DataFrame, output_path: Path) -> None:
    report_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Report saved -> %s", output_path)


def print_summary(report_df: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("  OUTLIER DETECTION REPORT – SUMMARY")
    print("=" * 70)
    print(f"  {'Column':<28} {'Method':<10} {'Outlier Count':>14} {'%':>8}")
    print("  " + "-" * 64)
    for _, row in report_df.iterrows():
        indicator = " (!)" if row["Percentage"] > 5.0 else "    "
        print(f"  {row['Column']:<28} {row['Method']:<10} {row['Outlier Count']:>14,} {row['Percentage']:>7.2f}%{indicator}")
    print("\n  (!) = column has > 5% outliers – warrants investigation")
    print("=" * 70 + "\n")


def run(
    dataset_path: Optional[Path] = None,
    report_path: Optional[Path] = None,
    target_columns: Optional[list] = None,
) -> pd.DataFrame:
    _dataset = dataset_path or DATASET_PATH
    _report = report_path or REPORT_PATH
    _targets = target_columns or TARGET_COLUMNS
    ensure_report_dir(_report.parent)
    df = load_dataset(_dataset)
    report_df = build_outlier_report(df, _targets)
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
        logger.exception("Unexpected error during outlier detection: %s", exc)
        sys.exit(2)