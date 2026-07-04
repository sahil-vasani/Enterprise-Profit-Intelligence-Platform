"""
metadata.py — Dataclasses for structured PostgreSQL database metadata.
"""

from dataclasses import dataclass, field


@dataclass
class ColumnMeta:
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False


@dataclass
class ForeignKeyMeta:
    column: str
    referenced_table: str
    referenced_column: str


@dataclass
class TableMeta:
    name: str
    schema: str
    columns: list[ColumnMeta] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeyMeta] = field(default_factory=list)
    row_count_estimate: int = 0


@dataclass
class DatabaseMetadata:
    database_name: str
    pg_version: str
    default_schema: str
    schemas: list[str] = field(default_factory=list)
    tables: list[TableMeta] = field(default_factory=list)
    loaded_at: str = ""

    def get_table(self, name: str, schema: str | None = None) -> TableMeta | None:
        """Return a TableMeta by name (and optionally schema)."""
        for t in self.tables:
            if t.name == name and (schema is None or t.schema == schema):
                return t
        return None

    def table_names(self, schema: str | None = None) -> list[str]:
        """Return all table names, optionally filtered by schema."""
        return [t.name for t in self.tables if schema is None or t.schema == schema]

    def column_names(self, table: str, schema: str | None = None) -> list[str]:
        """Return all column names for a given table."""
        t = self.get_table(table, schema)
        return [c.name for c in t.columns] if t else []
