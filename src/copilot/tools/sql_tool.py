"""
sql_tool.py — Tool for executing SQL queries against the database safely.
"""

import re
import time
from typing import Any, Dict

import pandas as pd

from database import execute_dataframe
from logger import get_logger

log = get_logger("sql_tool")

_BLOCKED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|COPY|VACUUM|CALL|DO|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLTool:
    """Tool to execute SQL queries and return DataFrames and metadata."""

    def __init__(self):
        self.name = "SQLTool"
        self.description = "Executes read-only SQL queries against the database."

    def _is_safe(self, query: str) -> bool:
        """Check if the query is a safe read-only operation."""
        upper = query.strip().upper()
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return False
        return not bool(_BLOCKED.search(query))

    def execute(self, query: str) -> Dict[str, Any]:
        """
        Execute the SQL query and return results.

        Returns:
            dict with keys: df, row_count, execution_time, error
        """
        log.info("SQLTool executing query: %s", query.strip()[:120])

        if not self._is_safe(query):
            err_msg = "Query blocked: Only read-only SELECT statements are permitted."
            log.warning(err_msg)
            return {"df": None, "row_count": 0, "execution_time": 0.0, "error": err_msg}

        start_time = time.perf_counter()
        try:
            df = execute_dataframe(query)
            exec_time = round(time.perf_counter() - start_time, 3)
            row_count = len(df)
            log.info("Query successful: %d rows in %.3fs", row_count, exec_time)
            return {"df": df, "row_count": row_count, "execution_time": exec_time, "error": ""}
        except Exception as e:
            exec_time = round(time.perf_counter() - start_time, 3)
            err_msg = str(e)
            log.error("Query failed (%.3fs): %s", exec_time, err_msg)
            return {"df": None, "row_count": 0, "execution_time": exec_time, "error": err_msg}
