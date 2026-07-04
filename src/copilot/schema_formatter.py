"""
schema_formatter.py — Converts DatabaseMetadata into a clean,
prompt-ready text representation for SQL generation.
"""

from metadata import DatabaseMetadata, TableMeta


def _format_table(table: TableMeta) -> str:
    lines = [f"Table: {table.name}"]
    if table.row_count_estimate > 0:
        lines[0] += f"  (~{table.row_count_estimate:,} rows)"

    lines.append("  Columns:")
    for col in table.columns:
        flags = []
        if col.is_primary_key:
            flags.append("PK")
        # Check if this column is a FK
        fk_map = {fk.column: fk for fk in table.foreign_keys}
        if col.name in fk_map:
            fk = fk_map[col.name]
            flags.append(f"FK → {fk.referenced_table}.{fk.referenced_column}")
        nullable_tag = "NULL" if col.nullable else "NOT NULL"
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"    - {col.name:<30} {col.data_type:<20} {nullable_tag}{flag_str}"
        )

    return "\n".join(lines)


def _format_relationships(tables: list[TableMeta]) -> str:
    lines = []
    for table in tables:
        for fk in table.foreign_keys:
            lines.append(
                f"  {table.name}.{fk.column} → {fk.referenced_table}.{fk.referenced_column}"
            )
    if not lines:
        return ""
    return "Foreign Key Relationships:\n" + "\n".join(lines)


def format_schema(metadata: DatabaseMetadata) -> str:
    """
    Convert DatabaseMetadata into a human-readable, prompt-ready schema string.
    """
    sections = [
        f"Database: {metadata.database_name}",
        f"PostgreSQL Version: {metadata.pg_version}",
        f"Default Schema: {metadata.default_schema}",
        f"Total Tables: {len(metadata.tables)}",
        f"Schema Loaded At: {metadata.loaded_at}",
    ]

    # Group tables by schema
    schema_groups: dict[str, list[TableMeta]] = {}
    for table in metadata.tables:
        schema_groups.setdefault(table.schema, []).append(table)

    for schema_name, tables in sorted(schema_groups.items()):
        sections.append(f"\n=== Schema: {schema_name} ===\n")
        for table in tables:
            sections.append(_format_table(table))
            sections.append("")  # blank line between tables

        rel_block = _format_relationships(tables)
        if rel_block:
            sections.append(rel_block)

    return "\n".join(sections)
