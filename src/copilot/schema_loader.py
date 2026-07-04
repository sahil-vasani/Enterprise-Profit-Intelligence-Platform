"""
schema_loader.py — Queries PostgreSQL information_schema and pg_catalog
to build a complete DatabaseMetadata object.
"""

from datetime import datetime
from sqlalchemy import text

from database import get_engine
from metadata import ColumnMeta, DatabaseMetadata, ForeignKeyMeta, TableMeta
from logger import get_logger

log = get_logger("schema_loader")

_Q_DB_INFO = """
SELECT current_database() AS db_name, version() AS pg_version, current_schema() AS default_schema;
"""

_Q_SCHEMAS = """
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY schema_name;
"""

_Q_TABLES = """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_type IN ('BASE TABLE', 'VIEW')
  AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY table_schema, table_name;
"""

_Q_COLUMNS = """
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable
FROM information_schema.columns c
WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY c.table_schema, c.table_name, c.ordinal_position;
"""

_Q_PRIMARY_KEYS = """
SELECT
    tc.table_schema,
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position;
"""

_Q_FOREIGN_KEYS = """
SELECT
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    ccu.table_name  AS referenced_table,
    ccu.column_name AS referenced_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY tc.table_schema, tc.table_name;
"""

_Q_ROW_COUNTS = """
SELECT
    n.nspname  AS schema_name,
    c.relname  AS table_name,
    c.reltuples::BIGINT AS row_estimate
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'v')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast');
"""


def load_metadata() -> DatabaseMetadata:
    """Inspect the connected PostgreSQL database and return a DatabaseMetadata object."""
    engine = get_engine()
    log.info("Loading database metadata from information_schema...")

    with engine.connect() as conn:
        # ── Basic DB info ──────────────────────────────────────────────────────
        row = conn.execute(text(_Q_DB_INFO)).mappings().fetchone()
        db_name = row["db_name"]
        pg_version = row["pg_version"].split(",")[0].strip()
        default_schema = row["default_schema"] or "public"

        # ── Schemas ───────────────────────────────────────────────────────────
        schemas = [r["schema_name"] for r in conn.execute(text(_Q_SCHEMAS)).mappings()]

        # ── Tables ────────────────────────────────────────────────────────────
        table_index: dict[tuple[str, str], TableMeta] = {}
        for r in conn.execute(text(_Q_TABLES)).mappings():
            key = (r["table_schema"], r["table_name"])
            table_index[key] = TableMeta(
                name=r["table_name"],
                schema=r["table_schema"],
            )

        # ── Columns ───────────────────────────────────────────────────────────
        for r in conn.execute(text(_Q_COLUMNS)).mappings():
            key = (r["table_schema"], r["table_name"])
            if key not in table_index:
                continue
            table_index[key].columns.append(
                ColumnMeta(
                    name=r["column_name"],
                    data_type=r["data_type"],
                    nullable=(r["is_nullable"] == "YES"),
                )
            )

        # ── Primary Keys ──────────────────────────────────────────────────────
        for r in conn.execute(text(_Q_PRIMARY_KEYS)).mappings():
            key = (r["table_schema"], r["table_name"])
            if key not in table_index:
                continue
            col_name = r["column_name"]
            table_index[key].primary_keys.append(col_name)
            for col in table_index[key].columns:
                if col.name == col_name:
                    col.is_primary_key = True

        # ── Foreign Keys ──────────────────────────────────────────────────────
        for r in conn.execute(text(_Q_FOREIGN_KEYS)).mappings():
            key = (r["table_schema"], r["table_name"])
            if key not in table_index:
                continue
            table_index[key].foreign_keys.append(
                ForeignKeyMeta(
                    column=r["column_name"],
                    referenced_table=r["referenced_table"],
                    referenced_column=r["referenced_column"],
                )
            )

        # ── Row Count Estimates ───────────────────────────────────────────────
        for r in conn.execute(text(_Q_ROW_COUNTS)).mappings():
            key = (r["schema_name"], r["table_name"])
            if key in table_index:
                table_index[key].row_count_estimate = max(0, int(r["row_estimate"]))

    tables = list(table_index.values())
    log.info(
        "Metadata loaded: db=%s | schema=%s | tables=%d",
        db_name, default_schema, len(tables),
    )

    return DatabaseMetadata(
        database_name=db_name,
        pg_version=pg_version,
        default_schema=default_schema,
        schemas=schemas,
        tables=tables,
        loaded_at=datetime.now().isoformat(timespec="seconds"),
    )
