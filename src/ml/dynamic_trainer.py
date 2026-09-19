"""
dynamic_trainer.py — Multi-target dynamic ML training & prediction engine.

Flow
----
1. predict(target, horizon_days, confidence) is called by prediction_agent.
2. Check if  models/{target}_model.pkl  exists  → load (cache HIT, fast).
3. If not    → select_features() removes leakage and high-correlation cols
             → train RandomForest → save artifacts → proceed.
4. Build a "typical order" feature vector from stored medians.
5. Use per-tree predictions from RandomForest for confidence interval.
6. Scale per-order prediction to horizon (avg_orders_per_day × horizon_days).
7. Return a structured result dict consumed by prediction_agent.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

log = logging.getLogger("dynamic_trainer")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_PATH: Path = PROJECT_ROOT / "data" / "processed" / "amazon_enterprise_dataset.csv"
MODEL_DIR: Path = PROJECT_ROOT / "models"

RANDOM_STATE = 42

# Drop feature if |correlation with target| is above this threshold.
CORR_THRESHOLD: float = 0.95

# ── Leakage map ───────────────────────────────────────────────────────────────
# For each target, list the columns that are mathematically derived from or
# directly feed into that target — they must never be used as features.
LEAKAGE_MAP: dict[str, set[str]] = {
    "net_profit": {
        "gross_profit", "profit_margin_pct", "profit_leakage",
        "contribution_margin", "product_profitability_score",
        "campaign_roi", "gross_margin_pct",
    },
    "Amount": {
        "cogs", "gross_profit", "net_profit", "profit_margin_pct",
        "discount_cost", "platform_commission", "gross_margin_pct",
        "profit_leakage", "campaign_roi", "contribution_margin",
        "product_profitability_score", "attributed_revenue",
        "payment_gateway_fee",
    },
    "gross_profit": {
        "net_profit", "profit_margin_pct", "profit_leakage",
        "gross_margin_pct", "contribution_margin",
        "product_profitability_score", "cogs",
    },
    "shipping_cost": {
        "fuel_surcharge", "shipping_insurance", "reverse_logistics_cost",
        "estimated_shipping_distance",
    },
    "refund_amount": {
        "refurbishment_cost", "refund_processing_cost",
        "reverse_logistics_cost", "net_profit", "profit_leakage",
        "return_probability",
    },
    "cogs": {
        "gross_profit", "gross_margin_pct", "net_profit",
        "profit_margin_pct", "profit_leakage", "contribution_margin",
        "product_profitability_score", "platform_commission",
        "inventory_holding_cost",
    },
}

# Columns that are IDs, free text, or dates — never use as features.
_ALWAYS_EXCLUDE: set[str] = {
    "Order ID", "Date", "SKU", "Style", "ASIN", "ship-postal-code",
    "ship-country", "fulfilled-by", "promotion-ids", "currency",
    "Courier Status", "customer_id", "campaign_name", "return_reason",
    "index",
}

# Z-scores for common confidence levels.
_Z_SCORES: dict[float, float] = {0.80: 1.282, 0.90: 1.645, 0.95: 1.960, 0.99: 2.576}

# One-hot encode only low-cardinality categoricals.
_MAX_CARDINALITY = 20


# ── Helper: model file paths ──────────────────────────────────────────────────

def _model_files(target: str) -> tuple[Path, Path, Path]:
    """Return (model, feature_columns, medians) .pkl paths for a given target."""
    safe = target.replace(" ", "_").replace("/", "_")
    return (
        MODEL_DIR / f"{safe}_model.pkl",
        MODEL_DIR / f"{safe}_feature_columns.pkl",
        MODEL_DIR / f"{safe}_column_medians.pkl",
    )


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Processed dataset not found: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH, low_memory=False)
    log.info("Dataset loaded: %d rows x %d cols", *df.shape)
    return df


# ── Feature selection ─────────────────────────────────────────────────────────

def select_features(df: pd.DataFrame, target: str) -> tuple[list[str], list[str]]:
    """
    Auto-select clean features for `target`.

    Steps:
    1. Exclude ID/date/text columns.
    2. Exclude known leakage columns (LEAKAGE_MAP).
    3. Exclude features with |correlation| >= CORR_THRESHOLD to target.
    4. Split into numeric and low-cardinality categorical lists.

    Returns
    -------
    numeric_features, categorical_features
    """
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found in the dataset.")

    # Build exclusion set
    exclude: set[str] = _ALWAYS_EXCLUDE | {target}
    exclude |= LEAKAGE_MAP.get(target, set())

    target_series = df[target].dropna()

    # ── Numeric features ──────────────────────────────────────────────────────
    numeric_candidates = [
        c for c in df.select_dtypes(include=[np.number]).columns
        if c not in exclude
    ]

    clean_numeric: list[str] = []
    dropped_corr: list[tuple[str, float]] = []

    for col in numeric_candidates:
        col_clean = df[col].dropna()
        ts, cs = target_series.align(col_clean, join="inner")
        if len(ts) < 10:
            continue
        corr = float(ts.corr(cs))
        if abs(corr) >= CORR_THRESHOLD:
            dropped_corr.append((col, round(corr, 3)))
        else:
            clean_numeric.append(col)

    if dropped_corr:
        log.info(
            "Dropped high-correlation features (|r| >= %.2f): %s",
            CORR_THRESHOLD,
            dropped_corr,
        )

    # ── Categorical features ──────────────────────────────────────────────────
    cat_candidates = [
        c for c in df.select_dtypes(include=["object", "category"]).columns
        if c not in exclude
    ]
    clean_cat = [
        c for c in cat_candidates
        if df[c].nunique() <= _MAX_CARDINALITY
    ]

    log.info(
        "Feature selection for '%s': %d numeric + %d categorical",
        target, len(clean_numeric), len(clean_cat),
    )
    return clean_numeric, clean_cat


# ── Preprocessing ─────────────────────────────────────────────────────────────

def _preprocess(
    df: pd.DataFrame,
    target: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> tuple[pd.DataFrame, pd.Series, dict[str, float], list[str]]:
    """Impute missing values, encode categoricals, return X, y, medians, feature_cols."""
    df = df.copy()

    # Standard business imputation
    if "fulfilled-by" in df.columns:
        df["fulfilled-by"] = df["fulfilled-by"].fillna("Amazon")
    if "promotion-ids" in df.columns:
        df["promotion-ids"] = df["promotion-ids"].fillna("No_Promotion")
    if "currency" in df.columns:
        df["currency"] = df["currency"].fillna("INR")
    if "Courier Status" in df.columns:
        df["Courier Status"] = df["Courier Status"].fillna("Unshipped")

    # Drop rows where target is null
    df = df.dropna(subset=[target]).reset_index(drop=True)

    # Median imputation for numeric features
    medians: dict[str, float] = {}
    for col in numeric_features:
        if col in df.columns:
            m = float(df[col].median())
            medians[col] = m
            df[col] = df[col].fillna(m)

    # Keep only the columns we need
    cols_present = [c for c in (numeric_features + categorical_features) if c in df.columns]
    df_filtered = df[cols_present + [target]]

    # One-hot encode categorical columns
    cats_present = [c for c in categorical_features if c in df_filtered.columns]
    if cats_present:
        df_encoded = pd.get_dummies(df_filtered, columns=cats_present, drop_first=True)
    else:
        df_encoded = df_filtered.copy()

    # Reconstruct final feature list
    encoded_extras = [c for c in df_encoded.columns if c not in numeric_features + [target]]
    feature_cols = [c for c in numeric_features if c in df_encoded.columns] + encoded_extras

    X = df_encoded[feature_cols]
    y = df_encoded[target]
    return X, y, medians, feature_cols


# ── Training ──────────────────────────────────────────────────────────────────

def train_for_target(target: str, df: Optional[pd.DataFrame] = None) -> dict[str, Any]:
    """
    Train a RandomForest model for `target` with auto feature selection.

    Saves three artifacts:
      - models/{target}_model.pkl
      - models/{target}_feature_columns.pkl
      - models/{target}_column_medians.pkl

    Returns
    -------
    dict with keys: target, r2, mae, features_used
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("Training new model for target: '%s'", target)

    if df is None:
        df = _load_data()

    numeric_features, categorical_features = select_features(df, target)

    if not numeric_features and not categorical_features:
        raise ValueError(f"No usable features found for target '{target}'.")

    X, y, medians, feature_cols = _preprocess(
        df, target, numeric_features, categorical_features
    )
    log.info("Feature matrix: %d rows x %d features", *X.shape)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE
    )

    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    r2 = round(float(r2_score(y_test, y_pred)), 4)
    mae = round(float(mean_absolute_error(y_test, y_pred)), 2)
    log.info("Training complete — R2: %.4f  |  MAE: %.2f", r2, mae)

    # Save all three artifacts
    model_path, feat_path, med_path = _model_files(target)
    joblib.dump(model, model_path)
    joblib.dump(feature_cols, feat_path)
    joblib.dump(medians, med_path)
    log.info("Artifacts saved -> %s", model_path.parent)

    return {"target": target, "r2": r2, "mae": mae, "features_used": len(feature_cols)}


# ── Model cache ───────────────────────────────────────────────────────────────

def _get_or_train(target: str) -> tuple[Any, list[str], dict[str, float], bool]:
    """
    Return (model, feature_cols, medians, was_cached).

    For net_profit: falls back to legacy best_model.pkl if the
    target-specific file does not exist yet.
    """
    model_path, feat_path, med_path = _model_files(target)

    # Legacy fallback for net_profit (trained by train_model.py)
    if target == "net_profit" and not model_path.exists():
        legacy_model = MODEL_DIR / "best_model.pkl"
        legacy_feat = MODEL_DIR / "feature_columns.pkl"
        legacy_med = MODEL_DIR / "column_medians.pkl"
        if legacy_model.exists() and legacy_feat.exists() and legacy_med.exists():
            log.info("net_profit: using legacy best_model.pkl (cache HIT)")
            return (
                joblib.load(legacy_model),
                joblib.load(legacy_feat),
                joblib.load(legacy_med),
                True,
            )

    # Standard cache check
    if model_path.exists() and feat_path.exists() and med_path.exists():
        log.info("Cache HIT  -> loading '%s' model", target)
        return (
            joblib.load(model_path),
            joblib.load(feat_path),
            joblib.load(med_path),
            True,
        )

    # Train on-demand
    log.info("Cache MISS -> training model for '%s'", target)
    train_for_target(target)
    return (
        joblib.load(model_path),
        joblib.load(feat_path),
        joblib.load(med_path),
        False,
    )


# ── Prediction ────────────────────────────────────────────────────────────────

def predict(
    target: str,
    horizon_days: int = 30,
    confidence: float = 0.90,
) -> dict[str, Any]:
    """
    Predict the total value of `target` over `horizon_days` with a
    confidence interval.

    Strategy
    --------
    1. Load (or train) the per-order model for `target`.
    2. Build a "typical order" feature vector from stored medians.
    3. Get per-tree predictions from RandomForest  →  mean and std.
    4. Scale to horizon: per_order_value x avg_orders_per_day x horizon_days.
    5. Apply z-score CI: [mean - z*std, mean + z*std] x scale.

    Returns
    -------
    {
      target, horizon_days, confidence,
      prediction, lower_bound, upper_bound,
      per_order_prediction,
      model_was_cached, features_used, daily_orders
    }
    """
    model, feature_cols, medians, was_cached = _get_or_train(target)

    # Build typical-order feature vector from medians
    input_data = {col: medians.get(col, 0) for col in feature_cols}
    df_input = pd.DataFrame([input_data])

    # Per-order confidence interval via individual tree predictions
    if hasattr(model, "estimators_"):
        tree_preds = np.array(
            [tree.predict(df_input)[0] for tree in model.estimators_]
        )
        per_order_mean = float(tree_preds.mean())
        per_order_std = float(tree_preds.std())
    else:
        per_order_mean = float(model.predict(df_input)[0])
        per_order_std = abs(per_order_mean) * 0.05  # 5% fallback

    # Compute avg daily orders from the full dataset
    df_raw = _load_data()
    df_raw["_date"] = pd.to_datetime(df_raw["Date"], format="%m-%d-%y", errors="coerce")
    total_days = max(
        (df_raw["_date"].max() - df_raw["_date"].min()).days, 1
    )
    avg_orders_per_day = len(df_raw) / total_days

    # Scale factor: avg daily orders x forecast horizon
    scale = avg_orders_per_day * horizon_days

    # Z-score for requested confidence level
    z = _Z_SCORES.get(round(confidence, 2), 1.960)

    prediction = round(per_order_mean * scale, 2)
    lower_bound = round((per_order_mean - z * per_order_std) * scale, 2)
    upper_bound = round((per_order_mean + z * per_order_std) * scale, 2)

    log.info(
        "Prediction '%s' / %d days: %.2f  [%.2f – %.2f]  @ %.0f%% CI",
        target, horizon_days, prediction, lower_bound, upper_bound, confidence * 100,
    )

    return {
        "target": target,
        "horizon_days": horizon_days,
        "confidence": confidence,
        "prediction": prediction,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "per_order_prediction": round(per_order_mean, 2),
        "model_was_cached": was_cached,
        "features_used": len(feature_cols),
        "daily_orders": round(avg_orders_per_day, 1),
    }
