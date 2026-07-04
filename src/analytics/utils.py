"""
utils.py — Shared utilities for the Enterprise Profit Intelligence Platform.
Provides constants, formatters, chart saving, data loading, logging, and validation
used by all analytics modules.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_PATH  = Path("data/processed/amazon_enterprise_dataset.csv")
REPORT_DIR = Path("reports/analytics")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── Chart DPI ─────────────────────────────────────────────────────────────────
CHART_DPI = 150

# ── Brand colours shared across all modules ───────────────────────────────────
COLORS: dict[str, str] = {
    "blue":   "#1F3A5F",
    "red":    "#C0392B",
    "green":  "#1A7A4A",
    "orange": "#E67E22",
    "gray":   "#7F8C8D",
}

# ── Matplotlib chart defaults ─────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor":   "white",
    "axes.edgecolor":   "#CCCCCC", "axes.grid":       True,
    "grid.color":       "#E8E8E8", "grid.linewidth":  0.6,
    "font.family":      "DejaVu Sans", "font.size":   11,
    "axes.titlesize":   14, "axes.titleweight":       "bold",
    "axes.labelsize":   11, "xtick.labelsize":        10,
    "ytick.labelsize":  10,
})

# ── Internal logger used by save_chart ────────────────────────────────────────
_log = logging.getLogger("analytics")


# ── INR tick formatters ───────────────────────────────────────────────────────
def fmt_millions(value: float, _: int) -> str:
    """Format a value as INR millions (0 dp), e.g. ₹12M."""
    return f"₹{value / 1_000_000:.0f}M"


def fmt_millions_1dp(value: float, _: int) -> str:
    """Format a value as INR millions (1 dp), e.g. ₹12.3M."""
    return f"₹{value / 1_000_000:.1f}M"


def fmt_thousands(value: float, _: int) -> str:
    """Format a value as INR thousands, e.g. ₹450K."""
    return f"₹{value / 1_000:.0f}K"


def fmt_pct(value: float, _: int) -> str:
    """Format a value as integer percentage, e.g. 12%."""
    return f"{value:.0f}%"


def fmt_pct_1dp(value: float, _: int) -> str:
    """Format a value as percentage with one decimal, e.g. 12.3%."""
    return f"{value:.1f}%"


# ── Chart save helper ─────────────────────────────────────────────────────────
def save_chart(filename: str) -> None:
    """Save the current matplotlib figure to REPORT_DIR and close it."""
    plt.tight_layout()
    plt.savefig(REPORT_DIR / filename, dpi=CHART_DPI, bbox_inches="tight")
    plt.close()
    _log.info("  Saved: %s", filename)


# ── Dataset loader ────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    """Load the enterprise dataset and parse the Date column into periods."""
    df = pd.read_csv(DATA_PATH)
    df["Date"]  = pd.to_datetime(df["Date"], format="%m-%d-%y", errors="coerce")
    df["month"] = df["Date"].dt.to_period("M")
    return df


# ── Logging setup ─────────────────────────────────────────────────────────────
def setup_logging(name: str) -> logging.Logger:
    """Configure root logger to write plain messages to stdout and return a named logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger(name)


# ── Column validation ─────────────────────────────────────────────────────────
def validate_columns(df: pd.DataFrame, required: list[str], module: str) -> None:
    """Raise ValueError listing any columns that are absent from the dataset."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{module}] Missing required columns: {missing}")
