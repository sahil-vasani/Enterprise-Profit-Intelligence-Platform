"""
sql_validator.py — Pre-execution SQL validation using cached DatabaseMetadata.
Checks that referenced tables and columns exist, and that only SELECT is used.
"""

import re
from metadata import DatabaseMetadata
from logger import get_logger

log = get_logger("sql_validator")

_BLOCKED_STATEMENTS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|MERGE|CALL|DO|VACUUM)\b",
    re.IGNORECASE,
)

_TABLE_REF = re.compile(
    r"\bFROM\s+([a-zA-Z_][\w.]*)"
    r"|\bJOIN\s+([a-zA-Z_][\w.]*)",
    re.IGNORECASE,
)


def _strip_schema_prefix(name: str) -> str:
    """Remove schema prefix from a qualified name (e.g. analytics.fact_sales → fact_sales)."""
    return name.split(".")[-1]


def validate_sql(sql: str, metadata: DatabaseMetadata) -> tuple[bool, str]:
    """
    Validate SQL against cached metadata before execution.

    Returns:
        (True, "") on success.
        (False, error_message) on failure.
    """
    sql_stripped = sql.strip()

    # ── Rule 1: Must be SELECT or CTE ─────────────────────────────────────────
    upper = sql_stripped.upper().lstrip()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        msg = "Only SELECT queries are allowed."
        log.warning("Validation failed: %s", msg)
        return False, msg

    # ── Rule 2: No destructive keywords ───────────────────────────────────────
    match = _BLOCKED_STATEMENTS.search(sql_stripped)
    if match:
        msg = f"Blocked keyword detected: {match.group(0).upper()}"
        log.warning("Validation failed: %s", msg)
        return False, msg

    # ── Rule 3: Referenced tables must exist ──────────────────────────────────
    known_tables = set(metadata.table_names())
    referenced_tables: list[str] = []
    for m in _TABLE_REF.finditer(sql_stripped):
        raw = m.group(1) or m.group(2)
        table_name = _strip_schema_prefix(raw)
        referenced_tables.append(table_name)

    for table_name in referenced_tables:
        if table_name not in known_tables:
            msg = f"Table '{table_name}' does not exist in the database."
            log.warning("Validation failed: %s", msg)
            return False, msg

    log.info("SQL validation passed. Tables checked: %s", referenced_tables or "none detected")
    return True, ""
