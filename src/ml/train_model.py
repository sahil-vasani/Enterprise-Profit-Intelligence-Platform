"""
train_model.py — Stage 8 Business Machine Learning Module.
Trains and evaluates ML models to predict net profit at the order level.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from xgboost import XGBRegressor

# Force UTF-8 stdout encoding for clean console printouts
sys.stdout.reconfigure(encoding="utf-8")

# Configure simple stdout logging
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("ml")

# ── Configuration Constants ──────────────────────────────────────────────────
DATA_PATH = Path("data/processed/amazon_enterprise_dataset.csv")
MODEL_DIR = Path("models")
REPORT_DIR = Path("reports/ml")

RANDOM_STATE = 42
TARGET = "net_profit"
TEST_SPLIT_RATIO = 0.15
VAL_SPLIT_RATIO = 0.1765  # 0.1765 of 0.85 is ~0.15 of total dataset size
CV_FOLDS = 3
SEARCH_ITERATIONS = 15
TOP_FEATURE_COUNT = 15
FIGURE_DPI = 150
FIG_SIZE_DEFAULT = (8, 6)
FIG_SIZE_LARGE = (10, 6)

NUMERIC_FEATURES = [
    "Qty", "Amount", "cogs", "estimated_shipping_distance", "shipping_cost",
    "delay_probability", "loyalty_score", "estimated_clv", "estimated_cac",
    "inventory_age_days", "inventory_turnover", "stockout_probability",
    "return_probability", "discount_cost", "campaign_cost", "campaign_roi",
    "product_profitability_score"
]

CATEGORICAL_FEATURES = [
    "Fulfilment", "Sales Channel", "ship-service-level", "Category", "Size",
    "B2B", "warehouse_zone", "courier_partner", "customer_segment",
    "acquisition_channel", "campaign_type", "velocity_class", "abc_class"
]

MODEL_CONFIG = {
    "random_forest": {
        "n_estimators": [30, 50],
        "max_depth": [5, 10, 15],
        "min_samples_split": [2, 5]
    },
    "xgboost": {
        "n_estimators": [50, 100],
        "max_depth": [3, 6, 8],
        "learning_rate": [0.01, 0.1, 0.2]
    },
    "lightgbm": {
        "n_estimators": [50, 100],
        "max_depth": [-1, 5, 10],
        "learning_rate": [0.01, 0.1, 0.2],
        "num_leaves": [15, 31, 63]
    }
}

# Mapping of features to their business interpretations and actions
FEATURE_INTERPRETATION = {
    "return_probability": {
        "desc": "Represents the estimated risk of a product return per order.",
        "action": "Enforce strict pre-shipment quality checks and size guides on high-risk items."
    },
    "campaign_cost": {
        "desc": "Captures the marketing overhead allocated to acquire orders.",
        "action": "Audit underperforming campaigns and reallocate budgets to high-ROI channels."
    },
    "cogs": {
        "desc": "Represents the direct cost of manufacturing/purchasing goods.",
        "action": "Negotiate volume discounts with vendors or optimize manufacturing processes."
    },
    "Amount": {
        "desc": "Represents the gross revenue value generated per transaction.",
        "action": "Upsell or bundle premium accessories to increase the average order size."
    },
    "campaign_roi": {
        "desc": "Calculates the revenue yield generated relative to campaign spend.",
        "action": "Scale high-performing ad creatives and discontinue sub-1.5x ROI campaigns."
    },
    "shipping_cost": {
        "desc": "Indicates courier freight fees to deliver the order to destination.",
        "action": "Renegotiate courier SLA contracts and optimize packaging dimensions."
    },
    "discount_cost": {
        "desc": "Captures margin leakage from promotional coupons.",
        "action": "Implement dynamic, conditional discounts instead of blanket sitewide codes."
    }
}


# ── Reusable I/O Helpers ──────────────────────────────────────────────────────
def create_dir(path: Path) -> None:
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: Path, index: bool = False, index_label: str = None) -> None:
    """Save a pandas DataFrame to a CSV file."""
    create_dir(path.parent)
    df.to_csv(path, index=index, index_label=index_label)


def save_plot(filename: str) -> None:
    """Apply tight layout, save matplotlib figure to REPORT_DIR, and close it."""
    plt.tight_layout()
    create_dir(REPORT_DIR)
    plt.savefig(REPORT_DIR / filename, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close()


# ── Data Validation & Preprocessing ─────────────────────────────────────────
def validate_dataset(df: pd.DataFrame) -> None:
    """Validate dataset properties: exists, not empty, target, features, duplicates, and null target."""
    if df.empty:
        raise ValueError("Dataset validation failed: The processed dataset is empty.")
    if TARGET not in df.columns:
        raise ValueError(f"Dataset validation failed: Target column '{TARGET}' not found.")
    if df[TARGET].isnull().any():
        raise ValueError(f"Dataset validation failed: Target column '{TARGET}' contains null values.")
    if df.columns.duplicated().any():
        duplicated_cols = df.columns[df.columns.duplicated()].tolist()
        raise ValueError(f"Dataset validation failed: Duplicate column names detected: {duplicated_cols}")

    missing_cols = [c for c in NUMERIC_FEATURES + CATEGORICAL_FEATURES if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset validation failed: Missing required columns: {missing_cols}")


def load_and_preprocess() -> tuple[pd.DataFrame, pd.Series, dict[str, float], list[str]]:
    """Load the dataset, perform validation, imputation, and encoding."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset path '{DATA_PATH}' does not exist.")

    df = pd.read_csv(DATA_PATH)
    validate_dataset(df)

    # Impute missing numeric values using column medians and capture medians
    medians: dict[str, float] = {}
    for col in NUMERIC_FEATURES:
        median_val = float(df[col].median())
        medians[col] = median_val
        df[col] = df[col].fillna(median_val)

    # Filter columns to minimize memory footprint
    cols_to_keep = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    df_filtered = df[cols_to_keep]

    # One-hot encode categorical variables
    df_encoded = pd.get_dummies(df_filtered, columns=CATEGORICAL_FEATURES, drop_first=True)

    # Reconstruct exact feature list matching final dummy column layout
    encoded_cols = [c for c in df_encoded.columns if c not in NUMERIC_FEATURES + [TARGET]]
    feature_cols = NUMERIC_FEATURES + encoded_cols

    X = df_encoded[feature_cols]
    y = df_encoded[TARGET]
    return X, y, medians, feature_cols


def split_data(
    X: pd.DataFrame, y: pd.Series
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Split features and target into train (70%), validation (15%), and test (15%)."""
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=TEST_SPLIT_RATIO, random_state=RANDOM_STATE
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=VAL_SPLIT_RATIO, random_state=RANDOM_STATE
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


# ── Model Training & Tuning ──────────────────────────────────────────────────
def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Mean Absolute Percentage Error (MAPE) handling division by zero."""
    safe_true = np.where(y_true == 0, 1e-5, y_true)
    return float(np.mean(np.abs((y_true - y_pred) / safe_true)) * 100)


def evaluate_model(model: Any, X_eval: pd.DataFrame, y_eval: pd.Series) -> dict[str, float]:
    """Evaluate a trained model on evaluation features and target."""
    preds = model.predict(X_eval)
    mae = float(mean_absolute_error(y_eval, preds))
    rmse = float(np.sqrt(mean_squared_error(y_eval, preds)))
    r2 = float(r2_score(y_eval, preds))
    mape = calculate_mape(y_eval.values, preds)
    return {"MAE": mae, "RMSE": rmse, "R2": r2, "MAPE": mape}


def run_random_search(model: Any, param_dist: dict[str, Any], X_tr: pd.DataFrame, y_tr: pd.Series) -> Any:
    """Run 3-fold RandomizedSearchCV on the estimator using configuration values."""
    search = RandomizedSearchCV(
        model,
        param_distributions=param_dist,
        n_iter=SEARCH_ITERATIONS,
        cv=CV_FOLDS,
        scoring="neg_root_mean_squared_error",
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
    search.fit(X_tr, y_tr)
    return search.best_estimator_


def train_all_models(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Train baseline and tuned tree models, returning estimator dict and performance DF."""
    lr_model = LinearRegression()
    lr_model.fit(X_train, y_train)

    rf_best = run_random_search(
        RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1),
        MODEL_CONFIG["random_forest"], X_train, y_train
    )

    xgb_best = run_random_search(
        XGBRegressor(random_state=RANDOM_STATE, n_jobs=-1, tree_method="hist"),
        MODEL_CONFIG["xgboost"], X_train, y_train
    )

    lgb_best = run_random_search(
        LGBMRegressor(random_state=RANDOM_STATE, n_jobs=-1, verbosity=-1),
        MODEL_CONFIG["lightgbm"], X_train, y_train
    )

    models = {"Linear Regression": lr_model, "Random Forest": rf_best, "XGBoost": xgb_best, "LightGBM": lgb_best}
    results = {name: evaluate_model(model, X_test, y_test) for name, model in models.items()}
    comparison_df = pd.DataFrame(results).T

    return models, comparison_df


# ── Feature Importance & Diagnostics ──────────────────────────────────────────
def get_feature_importances(model: Any, feature_names: list[str]) -> np.ndarray:
    """Extract feature importances or model coefficients as an array."""
    if hasattr(model, "feature_importances_"):
        return np.array(model.feature_importances_)
    if hasattr(model, "coef_"):
        return np.abs(model.coef_)
    return np.zeros(len(feature_names))


def export_feature_importances(best_model: Any, feature_names: list[str]) -> None:
    """Plot top features and export sorted feature importance CSV."""
    importances = get_feature_importances(best_model, feature_names)
    importance_df = pd.DataFrame({
        "Feature": feature_names,
        "Importance": importances
    }).sort_values(by="Importance", ascending=False).reset_index(drop=True)

    save_csv(importance_df, REPORT_DIR / "feature_importance.csv", index=False)

    top_n = importance_df.head(TOP_FEATURE_COUNT)
    plt.figure(figsize=FIG_SIZE_LARGE)
    plt.barh(top_n["Feature"][::-1], top_n["Importance"][::-1], color="#1F3A5F", edgecolor="none")
    plt.title(f"Top {TOP_FEATURE_COUNT} Feature Importances (Business Drivers)")
    plt.xlabel("Importance / Weight Score")
    plt.grid(axis="x", linestyle="--", alpha=0.7)
    save_plot("feature_importance.png")


def plot_diagnostics(best_model: Any, X_te: pd.DataFrame, y_te: pd.Series) -> None:
    """Plot and save Actual vs Predicted, Residuals, and error histogram."""
    preds = best_model.predict(X_te)
    residuals = y_te - preds

    # Actual vs Predicted Plot
    plt.figure(figsize=FIG_SIZE_DEFAULT)
    plt.scatter(y_te, preds, alpha=0.3, color="#1A7A4A", edgecolors="none")
    plt.plot([y_te.min(), y_te.max()], [y_te.min(), y_te.max()], "k--", lw=2)
    plt.title("Actual vs Predicted Net Profit")
    plt.xlabel("Actual Net Profit (₹)")
    plt.ylabel("Predicted Net Profit (₹)")
    plt.grid(linestyle="--", alpha=0.7)
    save_plot("actual_vs_predicted.png")

    # Residuals Plot
    plt.figure(figsize=FIG_SIZE_DEFAULT)
    plt.scatter(preds, residuals, alpha=0.3, color="#C0392B", edgecolors="none")
    plt.axhline(y=0, color="black", linestyle="--", lw=2)
    plt.title("Residual Analysis")
    plt.xlabel("Predicted Net Profit (₹)")
    plt.ylabel("Residuals (₹)")
    plt.grid(linestyle="--", alpha=0.7)
    save_plot("residual_plot.png")

    # Prediction Error Histogram Plot
    plt.figure(figsize=FIG_SIZE_DEFAULT)
    plt.hist(residuals, bins=50, color="#E67E22", edgecolor="white", alpha=0.8)
    plt.axvline(x=0, color="black", linestyle="--", lw=2)
    plt.title("Prediction Error Distribution")
    plt.xlabel("Residual Error Value (₹)")
    plt.ylabel("Frequency")
    plt.grid(linestyle="--", alpha=0.7)
    save_plot("residual_histogram.png")


# ── Reports & Serialization ──────────────────────────────────────────────────
def save_model_summary(
    best_model_name: str, metrics: dict[str, float], feature_names: list[str], best_model: Any
) -> None:
    """Save performance metrics, detailed business drivers, and recommendations."""
    importances = get_feature_importances(best_model, feature_names)
    indices = np.argsort(importances)[::-1]

    drivers_str = ""
    for idx, i in enumerate(indices[:5], 1):
        feature = feature_names[i]
        pct = importances[i] * 100
        mapping = FEATURE_INTERPRETATION.get(
            feature,
            {
                "desc": "Impacts customer segment pricing and purchasing patterns.",
                "action": "Tailor promotional pricing and regional courier partner selection."
            }
        )
        drivers_str += (
            f"{idx}. {feature} (Importance: {pct:.2f}%)\n"
            f"   - Interpretation: {mapping['desc']}\n"
            f"   - Action: {mapping['action']}\n\n"
        )

    summary_content = (
        "==================================================\n"
        "STAGE 8 — BUSINESS MACHINE LEARNING SUMMARY REPORT\n"
        "==================================================\n\n"
        "BEST MODEL DETAILS:\n"
        f"Model Name           : {best_model_name}\n"
        f"Root Mean Sq Error   : {metrics['RMSE']:.4f}\n"
        f"Mean Absolute Error  : {metrics['MAE']:.4f}\n"
        f"R-squared Score      : {metrics['R2']:.4f}\n"
        f"Mean Abs Pct Error   : {metrics['MAPE']:.4f}%\n\n"
        "TOP BUSINESS DRIVERS:\n"
        f"{drivers_str}"
        "MANAGEMENT RECOMMENDATIONS:\n"
        "R1. Prioritize resources on root-cause fixes for top drivers to recover profit margins.\n"
        "R2. Revise product pricing strategy for high-COGS SKUs to restore healthy margins.\n"
        "R3. Restructure regional delivery fees to mitigate high local shipping overhead.\n"
        "R4. Run targeted pre-shipment checks on high return-risk items.\n"
    )

    create_dir(REPORT_DIR)
    with open(REPORT_DIR / "ml_summary.txt", "w", encoding="utf-8") as f:
        f.write(summary_content)
    with open(REPORT_DIR / "business_insights.txt", "w", encoding="utf-8") as f:
        f.write(summary_content)


def persist_preprocessing_assets(medians: dict[str, float], feature_cols: list[str]) -> None:
    """Persist feature medians and column alignment lists for pipeline inference."""
    create_dir(MODEL_DIR)
    joblib.dump(medians, MODEL_DIR / "column_medians.pkl")
    joblib.dump(feature_cols, MODEL_DIR / "feature_columns.pkl")


# ── Executable Entrypoint ─────────────────────────────────────────────────────
def main() -> None:
    """Execute the end-to-end model training, optimization, and evaluation pipeline."""
    start_time = time.time()

    # 1. Load, validate, and preprocess
    X, y, medians, feature_cols = load_and_preprocess()
    log.info("Dataset Loaded")

    # 2. Train-Val-Test Split
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(X, y)
    log.info("Training Started")

    # 3. Model Training, Search & Optimization
    models, comparison_df = train_all_models(X_train, y_train, X_test, y_test)
    log.info("Training Finished")

    # 4. Show evaluation comparisons
    log.info("\nModel Comparison")
    log.info(comparison_df.to_string())

    # 5. Automatically select best model by lowest RMSE
    best_model_name = str(comparison_df["RMSE"].idxmin())
    best_model = models[best_model_name]
    best_metrics = comparison_df.loc[best_model_name].to_dict()

    log.info("\nBest Model")
    log.info("Model Name : %s", best_model_name)
    log.info("RMSE       : %.4f", best_metrics["RMSE"])
    log.info("MAE        : %.4f", best_metrics["MAE"])
    log.info("R²         : %.4f", best_metrics["R2"])

    # 6. Save model and preprocessing assets
    create_dir(MODEL_DIR)
    joblib.dump(best_model, MODEL_DIR / "best_model.pkl")
    persist_preprocessing_assets(medians, feature_cols)
    log.info("Model Saved")

    # 7. Diagnostic charts & sorted feature importances CSV
    plot_diagnostics(best_model, X_test, y_test)
    export_feature_importances(best_model, feature_cols)
    log.info("Charts Saved")

    # 8. Business summary report
    save_model_summary(best_model_name, best_metrics, feature_cols, best_model)
    log.info("Insights Saved")

    # 9. Comparison table CSV export
    save_csv(comparison_df, REPORT_DIR / "model_comparison.csv", index=True, index_label="Model")

    exec_time = time.time() - start_time
    log.info("Execution Time : %.2f seconds", exec_time)


if __name__ == "__main__":
    main()
