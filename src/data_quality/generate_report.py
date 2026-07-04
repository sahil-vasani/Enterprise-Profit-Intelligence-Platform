"""
generate_report.py – Master Summary Report Generator.
Orchestrates all four sub-modules, computes Data Quality Score (0–100), assigns grade.

Score weights (each 25 pts): Missing Values | Duplicate Rows | Outliers | Validation
Grades: 90-100 Excellent | 75-89 Good | 50-74 Fair | 0-49 Poor

Output: reports/data_quality/data_quality_summary.csv
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_quality.missing_values import run as run_missing
from src.data_quality.duplicate_check import run as run_duplicates
from src.data_quality.outlier_detection import run as run_outliers
from src.data_quality.data_validation import run as run_validation

DATASET_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
REPORT_DIR: Path = PROJECT_ROOT / "reports" / "data_quality"
SUMMARY_PATH: Path = REPORT_DIR / "data_quality_summary.csv"

WEIGHT_MISSING = WEIGHT_DUPLICATES = WEIGHT_OUTLIERS = WEIGHT_VALIDATION = 25.0
GRADE_EXCELLENT, GRADE_GOOD, GRADE_FAIR = 90.0, 75.0, 50.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_quality.generate_report")


def ensure_report_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_dataset_shape(csv_path: Path) -> tuple:
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    return df.shape[0], df.shape[1]


def compute_missing_score(missing_df: pd.DataFrame, weight: float) -> tuple:
    total_missing = int(missing_df["Missing Count"].sum())
    mean_pct = float(missing_df["Missing Percentage"].mean())
    score = round(weight * (1.0 - min(mean_pct / 100.0, 1.0)), 4)
    logger.info("Missing score: %.2f / %.1f  (mean missing pct: %.4f%%)", score, weight, mean_pct)
    return score, total_missing


def compute_duplicate_score(duplicate_df: pd.DataFrame, total_rows: int, weight: float) -> tuple:
    mask = duplicate_df["Duplicate Type"] == "Duplicate Rows (All Columns)"
    dup_row_count = int(duplicate_df.loc[mask, "Count"].values[0]) if mask.any() else 0
    score = round(weight * (1.0 - min(dup_row_count / total_rows, 1.0)) if total_rows > 0 else weight, 4)
    logger.info("Duplicate score: %.2f / %.1f  (duplicate rows: %d)", score, weight, dup_row_count)
    return score, dup_row_count


def compute_outlier_score(outlier_df: pd.DataFrame, weight: float) -> tuple:
    iqr_df = outlier_df[outlier_df["Method"] == "IQR"]
    total_outlier_count = int(iqr_df["Outlier Count"].sum())
    mean_pct = float(iqr_df["Percentage"].mean()) if not iqr_df.empty else 0.0
    score = round(weight * (1.0 - min(mean_pct / 100.0, 1.0)), 4)
    logger.info("Outlier score: %.2f / %.1f  (IQR total: %d, mean pct: %.4f%%)", score, weight, total_outlier_count, mean_pct)
    return score, total_outlier_count


def compute_validation_score(validation_df: pd.DataFrame, weight: float) -> tuple:
    evaluated = validation_df[validation_df["Status"] != "SKIP"]
    total_evaluated = len(evaluated)
    failed_rules = int((evaluated["Status"] == "FAIL").sum())
    pass_ratio = (total_evaluated - failed_rules) / total_evaluated if total_evaluated > 0 else 1.0
    score = round(weight * pass_ratio, 4)
    logger.info("Validation score: %.2f / %.1f  (%d/%d rules passed)", score, weight, total_evaluated - failed_rules, total_evaluated)
    return score, failed_rules


def assign_grade(score: float) -> str:
    if score >= GRADE_EXCELLENT: return "Excellent"
    if score >= GRADE_GOOD: return "Good"
    if score >= GRADE_FAIR: return "Fair"
    return "Poor"


def build_summary_dataframe(**kwargs) -> pd.DataFrame:
    return pd.DataFrame([{"Report Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **kwargs}])


def save_summary(summary_df: pd.DataFrame, output_path: Path) -> None:
    summary_df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Summary report saved -> %s", output_path)


def print_banner(overall_score: float, grade: str) -> None:
    grade_icon = {"Excellent": "[*****]", "Good": "[**** ]", "Fair": "[***  ]", "Poor": "[**   ]"}.get(grade, "[?????]")
    bar_filled = int(overall_score / 5)
    bar = "#" * bar_filled + "-" * (20 - bar_filled)
    print("\n" + "=" * 65)
    print("  DATA QUALITY FRAMEWORK – FINAL REPORT")
    print("=" * 65)
    print(f"  Overall Data Quality Score : {overall_score:>6.2f} / 100")
    print(f"  Quality Grade              : {grade}  {grade_icon}")
    print(f"  Score Bar                  : [{bar}]")
    print("=" * 65 + "\n")


def run(
    dataset_path: Optional[Path] = None,
    summary_path: Optional[Path] = None,
    report_dir: Optional[Path] = None,
) -> pd.DataFrame:
    _dataset = dataset_path or DATASET_PATH
    _summary = summary_path or SUMMARY_PATH
    _rdir = report_dir or REPORT_DIR

    ensure_report_dir(_rdir)

    logger.info("Reading dataset shape ...")
    total_rows, total_columns = get_dataset_shape(_dataset)

    # Run all four sub-modules
    missing_df   = run_missing(dataset_path=_dataset,   report_path=_rdir / "missing_values_report.csv")
    duplicate_df = run_duplicates(dataset_path=_dataset, report_path=_rdir / "duplicate_report.csv")
    outlier_df   = run_outliers(dataset_path=_dataset,  report_path=_rdir / "outlier_report.csv")
    validation_df = run_validation(dataset_path=_dataset, report_path=_rdir / "validation_report.csv")

    # Compute component scores
    missing_score,    total_missing_values = compute_missing_score(missing_df, WEIGHT_MISSING)
    duplicate_score,  duplicate_row_count  = compute_duplicate_score(duplicate_df, total_rows, WEIGHT_DUPLICATES)
    outlier_score,    total_outlier_count  = compute_outlier_score(outlier_df, WEIGHT_OUTLIERS)
    validation_score, validation_failures  = compute_validation_score(validation_df, WEIGHT_VALIDATION)

    overall_score = round(missing_score + duplicate_score + outlier_score + validation_score, 2)
    grade = assign_grade(overall_score)

    summary_df = build_summary_dataframe(
        **{
            "Total Rows": total_rows, "Total Columns": total_columns,
            "Total Missing Values": total_missing_values, "Duplicate Rows": duplicate_row_count,
            "Outlier Count (IQR)": total_outlier_count, "Validation Failures": validation_failures,
            "Missing Values Score (max 25)": missing_score, "Duplicate Score (max 25)": duplicate_score,
            "Outlier Score (max 25)": outlier_score, "Validation Score (max 25)": validation_score,
            "Overall Data Quality Score (0-100)": overall_score, "Quality Grade": grade,
        }
    )

    save_summary(summary_df, _summary)
    print_banner(overall_score, grade)

    print("  Component Score Breakdown:")
    for label, score, weight in [
        ("Missing Values", missing_score, WEIGHT_MISSING),
        ("Duplicate Rows", duplicate_score, WEIGHT_DUPLICATES),
        ("Outliers (IQR)", outlier_score, WEIGHT_OUTLIERS),
        ("Validation Rules", validation_score, WEIGHT_VALIDATION),
    ]:
        print(f"    {label:<30} {score:>6.2f} / {weight:.0f}")
    print(f"    {'-' * 38}")
    print(f"    {'TOTAL':<30} {overall_score:>6.2f} / 100")
    print(f"\n  Sub-reports saved to: {_rdir}")
    print(f"  Master summary saved: {_summary}\n")

    return summary_df


if __name__ == "__main__":
    try:
        run()
    except FileNotFoundError as exc:
        logger.error("Dataset not found: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Unexpected error during report generation: %s", exc)
        sys.exit(2)