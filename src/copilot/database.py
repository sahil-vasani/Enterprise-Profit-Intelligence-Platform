"""
database.py — PostgreSQL connection layer for the AI Business Copilot.
Uses SQLAlchemy for engine creation and simple query execution.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
import pandas as pd

from config import DATABASE_URL
from logger import get_logger

log = get_logger("database")

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine() -> Engine:
    """Create or return the SQLAlchemy engine singleton."""
    global _engine
    if _engine is None:
        # _engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
        _engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    connect_args={
        "options": "-csearch_path=analytics"
    }
)
        log.info("Database engine created.")
    return _engine


def get_session() -> Session:
    """Return a new database session."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()


def test_connection() -> bool:
    """Test database connectivity. Returns True on success."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Database connection successful.")
        return True
    except Exception as e:
        log.error("Database connection failed: %s", e)
        return False


def execute_query(sql: str) -> list[dict]:
    """Execute a read-only SQL query and return rows as a list of dicts."""
    with get_engine().connect() as conn:
        conn.execute(text("SET search_path TO analytics;"))
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    return rows


def execute_dataframe(sql: str) -> pd.DataFrame:
    """Execute a read-only SQL query and return a Pandas DataFrame."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SET search_path TO analytics;"))
            df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        log.error("Failed to execute query to DataFrame: %s", e)
        raise


def execute_scalar(sql: str):
    """Execute a read-only SQL query and return the first scalar value."""
    with get_engine().connect() as conn:
        conn.execute(text("SET search_path TO analytics;"))
        result = conn.execute(text(sql))
        return result.scalar()
