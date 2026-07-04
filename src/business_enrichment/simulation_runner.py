"""
simulation_runner.py — Enterprise Business Simulation Orchestrator
===================================================================

Entry point.  Reads the Amazon Sale Report CSV, runs each engine in
dependency order, and writes the extended enterprise dataset to disk.

Usage
-----
    python simulation_runner.py \\
        --input  "Amazon Sale Report.csv" \\
        --output "amazon_enterprise_dataset.csv" \\
        [--config business_config.yaml]

Each engine is run in the correct dependency order:
    1. logistics_engine   (shipping_cost used by finance + returns)
    2. customer_engine    (repeat_customer_flag used by returns)
    3. inventory_engine   (dead_stock_flag used by returns)
    4. returns_engine     (refund/disposal used by finance)
    5. marketing_engine   (marketing_attribution_cost used by finance)
    6. product_engine     (contribution_margin — uses shipping_cost)
    7. finance_engine     (full P&L — consumes all above)
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

# ── Engine imports ────────────────────────────────────────────────────────────
from logistics_engine  import run as run_logistics
from customer_engine   import run as run_customers
from inventory_engine  import run as run_inventory
from returns_engine    import run as run_returns
from marketing_engine  import run as run_marketing
from product_engine    import run as run_products
from finance_engine    import run as run_finance


# ─────────────────────────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _load_dataset(path: str) -> pd.DataFrame:
    """Load and minimally clean the Amazon Sale Report CSV."""
    _log(f"Loading dataset: {path}")
    df = pd.read_csv(
        path,
        dtype={"ship-postal-code": str},
        low_memory=False,
    )
    _log(f"  → {len(df):,} rows × {len(df.columns)} columns loaded")

    # Standardise column names (strip trailing spaces)
    df.columns = [c.strip() for c in df.columns]
    df.rename(columns={"Sales Channel ": "Sales Channel"}, inplace=True)

    # Drop the unnamed index column if present
    unnamed = [c for c in df.columns if c.startswith("Unnamed")]
    if unnamed:
        df.drop(columns=unnamed, inplace=True)

    # Coerce numeric columns
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df["Qty"]    = pd.to_numeric(df["Qty"],    errors="coerce").fillna(1.0)

    # Ensure B2B is string for consistency
    df["B2B"] = df["B2B"].astype(str)

    return df


def _validate_output(df: pd.DataFrame) -> None:
    """Quick sanity checks on the extended dataset."""
    original_cols = [
        "Order ID", "Date", "Status", "Fulfilment", "SKU",
        "Category", "Qty", "Amount", "ship-city", "ship-state"
    ]
    for col in original_cols:
        assert col in df.columns, f"ORIGINAL COLUMN MISSING: {col}"

    required_new = [
        "cogs", "gross_profit", "net_profit", "shipping_cost",
        "customer_id", "customer_segment", "return_probability",
        "inventory_available", "abc_class", "xyz_class",
    ]
    for col in required_new:
        assert col in df.columns, f"GENERATED COLUMN MISSING: {col}"

    _log(f"  ✓ Validation passed — {len(df.columns)} total columns")


# ─────────────────────────────────────────────────────────────────────────────
#  Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(input_path: str, output_path: str) -> pd.DataFrame:
    df = _load_dataset(input_path)
    enrichment_dir = Path("data/enrichment")
    enrichment_dir.mkdir(parents=True, exist_ok=True)
    steps = [
        ("Logistics Engine",  run_logistics),
        ("Customer Engine",   run_customers),
        ("Inventory Engine",  run_inventory),
        ("Returns Engine",    run_returns),
        ("Marketing Engine",  run_marketing),
        ("Product Engine",    run_products),
        ("Finance Engine",    run_finance),
    ]

    for name, engine_fn in steps:
        _log(f"Running {name} ...")
        t0 = time.time()

        df = engine_fn(df)

        _log(f"  → done in {time.time()-t0:.1f}s  |  columns: {len(df.columns)}")

        # Save snapshot after each engine
        filename = (
            name.lower()
                .replace(" ", "_")
                .replace("engine", "")
                .replace("__", "_")
                .strip("_")
        )

        df.to_csv(
            enrichment_dir / f"{filename}.csv",
            index=False
        )

    _log("Validating output ...")
    _validate_output(df)

    _log(f"Writing output → {output_path}")
    df.to_csv(output_path, index=False)
    _log(f"  ✓ Saved {len(df):,} rows × {len(df.columns)} columns")

    # ── Summary stats ─────────────────────────────────────────────────────────
    _log("\n══════════════ SIMULATION SUMMARY ══════════════")
    _log(f"  Total orders           : {len(df):,}")
    _log(f"  Total revenue (INR)    : {df['Amount'].sum():,.0f}")
    _log(f"  Total net profit (INR) : {df['net_profit'].sum():,.0f}")
    _log(f"  Avg profit margin      : {df['profit_margin_pct'].mean():.1f}%")
    _log(f"  Avg return probability : {df['return_probability'].mean()*100:.1f}%")
    _log(f"  Total profit leakage   : {df['profit_leakage'].sum():,.0f}")
    _log(f"  Unique customers       : {df['customer_id'].nunique():,}")
    _log(f"  Champion customers     : {(df['customer_segment']=='Champion').sum():,}")
    _log(f"  Dead stock flagged     : {df.get('dead_stock_flag', pd.Series(0)).sum():,} SKU rows")
    _log("════════════════════════════════════════════════\n")

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enterprise Business Simulation Engine — Amazon India Dataset Extender"
    )
    parser.add_argument(
        "--input",
        default="data/raw/Amazon Sale Report.csv",
        help="Path to Amazon Sale Report.csv",
    )

    parser.add_argument(
        "--output",
        default="data/processed/amazon_enterprise_dataset.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    run_simulation(args.input, args.output)


if __name__ == "__main__":
    main()
