"""
chart_builder.py — Shared chart + insight generation utility.
Used by sql_agent and analytics_agent after the business summary is complete.

Never raises: build_chart_from_df() wraps everything in try/except and returns
None on any failure so a chart issue never breaks the main answer.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.io as pio

from logger import get_logger

log = get_logger("chart_builder")

# ── Chart style matching src/ui/charts.py ────────────────────────────────────
_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
    font=dict(family="Inter, sans-serif", size=13),
)
_BAR_COLOR  = "#2563eb"
_LINE_COLOR = "#2563eb"
_PIE_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
               "#06b6d4", "#ec4899", "#84cc16"]

# ── Identifier column detection ───────────────────────────────────────────────

# Suffixes / exact names that mark a column as an identifier, not a metric.
_ID_SUFFIXES = ("_id", "id", "asin", "sku", "code", "key", "num", "no")

# Preferred business-metric column name fragments (checked via substring).
_METRIC_NAMES = (
    "total_sold", "sold", "revenue", "profit", "amount", "count",
    "qty", "quantity", "sales", "margin", "price", "cost", "spend",
    "orders", "units", "income", "gross", "net",
)


def _is_identifier_col(col_name: str) -> bool:
    """Return True if the column looks like an identifier rather than a metric."""
    name = col_name.lower().strip()
    # Exact matches
    if name in _ID_SUFFIXES:
        return True
    # Ends-with check (handles 'product_id', 'customer_id', etc.)
    for suffix in _ID_SUFFIXES:
        if name.endswith(suffix):
            return True
    return False


def _pick_metric_col(df: pd.DataFrame, exclude: set[str]) -> str | None:
    """
    Choose the best numeric metric column from df, skipping identifier-like
    columns and any column in *exclude*.

    Priority:
      1. First numeric column whose name contains a preferred metric keyword.
      2. First numeric column that is not an identifier.
      3. None (no safe metric found).
    """
    candidates = [
        col for col in df.columns
        if col not in exclude
        and not _is_identifier_col(col)
        and pd.api.types.is_numeric_dtype(df[col])
    ]
    # Priority 1 — preferred metric keyword match
    for col in candidates:
        name = col.lower()
        if any(kw in name for kw in _METRIC_NAMES):
            return col
    # Priority 2 — any non-id numeric column
    return candidates[0] if candidates else None


# ── Column classification helpers ─────────────────────────────────────────────

def _is_date_col(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if series.dtype == object:
        sample = series.dropna().head(5).astype(str)
        date_hints = ["jan", "feb", "mar", "apr", "may", "jun",
                      "jul", "aug", "sep", "oct", "nov", "dec",
                      "q1", "q2", "q3", "q4", "202", "201"]
        return any(any(h in v.lower() for h in date_hints) for v in sample)
    return False


def _is_id_valued(series: pd.Series) -> bool:
    """
    Return True if a numeric or object Series looks like it holds identifier
    values (large integers with no business meaning) rather than counts/amounts.
    Heuristic: integer dtype + column name ends in _id or is 'id',
    OR all values > 100 with very high variance relative to mean (auto-increment IDs).
    """
    name = series.name.lower() if hasattr(series, "name") else ""
    # Column name check — strongest signal
    if _is_identifier_col(name):
        return True
    # Numeric dtype check: if every value looks like a large integer ID
    if pd.api.types.is_integer_dtype(series):
        try:
            mn, mx = series.min(), series.max()
            # Large range with many distinct values → likely auto-increment IDs
            if mn >= 0 and mx > 1000 and series.nunique() / max(len(series), 1) > 0.8:
                return True
        except Exception:
            pass
    return False


def _find_sort_col(df: pd.DataFrame, date_col: str) -> str | None:
    """
    Given a recognised date/month-name column, look for a companion numeric
    ordering column (e.g. 'month', 'month_number', 'week', 'quarter', 'year')
    that can be used to sort the dataframe chronologically before plotting.
    Returns the column name or None.
    """
    order_hints = ("month_number", "month", "week", "quarter", "day", "year")
    for col in df.columns:
        if col == date_col:
            continue
        cname = col.lower()
        if any(cname == h or cname.endswith(h) for h in order_hints):
            if pd.api.types.is_numeric_dtype(df[col]):
                return col
    return None


def _find_cols(df: pd.DataFrame) -> tuple[str | None, str | None, str | None]:
    """Return (label_col, numeric_col, date_col) — any may be None.

    Rules:
    - Identifier-like columns (name or value pattern) are excluded from both
      the label axis and the metric axis.
    - A numeric column whose name or values look like IDs is never used as label.
    """
    label_col = date_col = None
    used: set[str] = set()

    # First pass — classify date and label columns
    for col in df.columns:
        series = df[col]
        if _is_date_col(series):
            if date_col is None:
                date_col = col
                used.add(col)
        elif not pd.api.types.is_numeric_dtype(series):
            # String/object column — use as label only if not id-like
            if label_col is None and not _is_identifier_col(col):
                label_col = col
                used.add(col)
            # If it IS id-like we skip it entirely (don't fall back to using it)
        else:
            # Numeric column — only use as label if it's genuinely categorical
            # (small unique count, not id-valued)
            if label_col is None and not _is_id_valued(series) and series.nunique() <= 20:
                # Could be a numeric category — skip for now, prefer string labels
                pass

    # Second pass — pick best metric column (excluding date/label cols)
    numeric_col = _pick_metric_col(df, used)

    return label_col, numeric_col, date_col


# ── Insight generation (template-first, LLM fallback) ────────────────────────

def _template_insight(df: pd.DataFrame, label_col: str | None,
                      numeric_col: str | None, date_col: str | None) -> str | None:
    """Try to produce a one-sentence insight without an LLM call."""
    try:
        if label_col and numeric_col:
            top_row = df.loc[df[numeric_col].idxmax()]
            top_label = top_row[label_col]
            top_val   = top_row[numeric_col]
            col_name  = numeric_col.replace("_", " ").title()
            return f"{top_label} generated the highest {col_name} at {top_val:,.0f}."
        if date_col and numeric_col:
            latest    = df.iloc[-1]
            prev      = df.iloc[-2] if len(df) > 1 else None
            val       = latest[numeric_col]
            col_name  = numeric_col.replace("_", " ").title()
            if prev is not None:
                direction = "up" if val >= prev[numeric_col] else "down"
                return f"{latest[date_col]} shows {col_name} of {val:,.0f}, {direction} from the prior period."
            return f"Latest {col_name}: {val:,.0f}."
        if numeric_col and len(df) == 1:
            # Single-row, no label — just state the metric value
            val      = df.iloc[0][numeric_col]
            col_name = numeric_col.replace("_", " ").title()
            return f"Result: {col_name} of {val:,.0f}."
    except Exception:
        pass
    return None


def generate_insight(df: pd.DataFrame, label_col: str | None,
                     numeric_col: str | None, date_col: str | None,
                     question: str = "") -> str:
    """
    Return a one-sentence insight string.
    Template-first; falls back to a short LLM call only when template
    cannot be derived from the DataFrame shape.
    """
    insight = _template_insight(df, label_col, numeric_col, date_col)
    if insight:
        return insight

    # LLM fallback — only reached for irregular shapes (>2 cols, no clear metric)
    try:
        from llm import get_llm
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        llm = get_llm()
        head_text = df.head(5).to_string(index=False)
        prompt = PromptTemplate(
            input_variables=["data", "question"],
            template=(
                "Data:\n{data}\n\n"
                "Write exactly ONE sentence (max 20 words) describing the most important finding "
                "from this data in response to: {question}\nInsight:"
            ),
        )
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"data": head_text, "question": question})
        return result.strip().split("\n")[0][:200]
    except Exception as e:
        log.warning("LLM insight fallback failed: %s", e)
        return ""


# ── Chart builder ─────────────────────────────────────────────────────────────

def build_chart_from_df(df: pd.DataFrame | None, question: str = "") -> dict | None:
    """
    Inspect a DataFrame and produce the best chart for it.

    Returns:
        {
            "chart_json":  str | None  (plotly.io.to_json output, or None for
                                        single-row results which should render
                                        as KPI callouts instead of charts),
            "table_rows":  list[dict]  (top ≤10 rows),
            "insight":     str,
        }
        or None if the DataFrame is empty, malformed, or has no chart-worthy shape.

    Single-row DataFrames: returns the dict WITHOUT chart_json (key absent / None)
    so callers can render a KPI callout instead of an empty chart.

    NEVER raises — all exceptions are caught and logged; callers get None.
    """
    try:
        if df is None or df.empty or len(df.columns) < 2:
            return None

        # Work on a clean copy; drop all-null columns
        df = df.dropna(axis=1, how="all").copy()
        if df.empty:
            return None

        label_col, numeric_col, date_col = _find_cols(df)

        if numeric_col is None:
            return None  # nothing to chart

        table_rows = df.head(10).to_dict(orient="records")
        insight    = generate_insight(df, label_col, numeric_col, date_col, question)

        # ── Single-row results: no chart (would be meaningless) ──────────────
        if len(df) <= 1:
            log.debug("Single-row result — skipping chart, returning KPI callout data.")
            return {
                "chart_json": None,
                "table_rows": table_rows,
                "insight":    insight,
            }

        fig = None

        # ── Line chart: date + numeric ─────────────────────────────────────
        if date_col and numeric_col:
            # Sort by a companion numeric ordering column (e.g. 'month') if
            # available — prevents Plotly from sorting month_name alphabetically.
            sort_col = _find_sort_col(df, date_col)
            if sort_col:
                # Keep year as primary sort if present, then the ordering col
                year_col = next(
                    (c for c in df.columns if c.lower() == "year"
                     and pd.api.types.is_numeric_dtype(df[c])),
                    None
                )
                sort_keys = ([year_col, sort_col] if year_col and year_col != sort_col
                             else [sort_col])
                df = df.sort_values(sort_keys).reset_index(drop=True)
                log.debug("Line chart: sorted by %s for chronological x-axis.", sort_keys)
            fig = px.line(
                df, x=date_col, y=numeric_col,
                title=numeric_col.replace("_", " ").title() + " Over Time",
                markers=True,
            )
            fig.update_traces(line_color=_LINE_COLOR, line_width=2)

        # ── Pie chart: label + numeric, ≤8 rows ───────────────────────────
        elif label_col and numeric_col and len(df) <= 8:
            fig = px.pie(
                df, names=label_col, values=numeric_col, hole=0.4,
                title=numeric_col.replace("_", " ").title() + " by " + label_col.replace("_", " ").title(),
                color_discrete_sequence=_PIE_COLORS,
            )

        # ── Horizontal bar: label + numeric, >8 rows ──────────────────────
        elif label_col and numeric_col:
            top_df = df.nlargest(min(15, len(df)), numeric_col)
            fig = px.bar(
                top_df, x=numeric_col, y=label_col,
                orientation="h",
                title="Top " + label_col.replace("_", " ").title()
                      + " by " + numeric_col.replace("_", " ").title(),
                color_discrete_sequence=[_BAR_COLOR],
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})

        if fig is None:
            return None

        fig.update_layout(**_LAYOUT)

        chart_json = pio.to_json(fig)

        return {
            "chart_json": chart_json,
            "table_rows": table_rows,
            "insight":    insight,
        }

    except Exception as e:
        log.warning("build_chart_from_df failed (chart skipped): %s", e)
        return None
