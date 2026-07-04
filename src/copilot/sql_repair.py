"""
sql_repair.py — LLM-powered SQL repair helper.
Packages the failed SQL, DB error, and schema into a repair prompt
and returns corrected SQL from the LLM.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from llm import get_llm
from logger import get_logger

log = get_logger("sql_repair")

_REPAIR_TEMPLATE = """You are an expert PostgreSQL SQL debugger.

A SQL query failed to execute. Your task is to generate a corrected SQL query.

ORIGINAL SQL:
{original_sql}

DATABASE ERROR:
{db_error}

DATABASE SCHEMA:
{schema}

RULES:
1. Output ONLY the corrected PostgreSQL SELECT query.
2. No markdown. No explanation. No ```sql``` blocks.
3. Fix only the error — do not rewrite the logic unnecessarily.
4. Use only tables and columns that exist in the DATABASE SCHEMA above.
5. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE.

Corrected SQL:"""

_REPAIR_PROMPT = PromptTemplate(
    input_variables=["original_sql", "db_error", "schema"],
    template=_REPAIR_TEMPLATE,
)


def repair_sql(original_sql: str, db_error: str, schema: str) -> str:
    """
    Ask the LLM to repair a failed SQL query.

    Args:
        original_sql: The SQL that failed.
        db_error:     The error message returned by PostgreSQL.
        schema:       The formatted schema string from schema_formatter.

    Returns:
        Corrected SQL string (markdown stripped).
    """
    log.info("Requesting SQL repair from LLM...")
    llm = get_llm()
    chain = _REPAIR_PROMPT | llm | StrOutputParser()
    repaired = chain.invoke({
        "original_sql": original_sql,
        "db_error": db_error,
        "schema": schema,
    })
    repaired = repaired.replace("```sql", "").replace("```", "").strip()
    log.info("SQL repair received from LLM.")
    return repaired
