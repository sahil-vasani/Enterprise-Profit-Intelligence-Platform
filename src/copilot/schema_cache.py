"""
schema_cache.py — In-memory singleton cache for DatabaseMetadata.
Loads once at application startup. Provides refresh_schema() to rebuild.
"""

from metadata import DatabaseMetadata
from schema_loader import load_metadata
from logger import get_logger

log = get_logger("schema_cache")

_cache: DatabaseMetadata | None = None


def load_schema_cache() -> DatabaseMetadata:
    """Load schema metadata into cache (only queries DB on first call)."""
    global _cache
    if _cache is not None:
        log.info("Schema cache already loaded (%d tables). Skipping reload.", len(_cache.tables))
        return _cache
    _cache = load_metadata()
    log.info(
        "Schema cache loaded: db=%s | schema=%s | tables=%d | loaded_at=%s",
        _cache.database_name,
        _cache.default_schema,
        len(_cache.tables),
        _cache.loaded_at,
    )
    return _cache


def refresh_schema() -> DatabaseMetadata:
    """Force a full reload of the schema metadata from the database."""
    global _cache
    log.info("Refreshing schema cache...")
    _cache = load_metadata()
    log.info(
        "Schema cache refreshed: db=%s | tables=%d | loaded_at=%s",
        _cache.database_name,
        len(_cache.tables),
        _cache.loaded_at,
    )
    return _cache


def get_schema_cache() -> DatabaseMetadata | None:
    """Return the cached DatabaseMetadata, or None if not yet loaded."""
    return _cache
