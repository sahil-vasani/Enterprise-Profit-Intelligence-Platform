"""
sql_agent.py — Agent pipeline for the SQL workflow.
Translates questions to SQL, validates, executes, auto-repairs on failure,
and generates business summaries. Schema is loaded from the live cache.
"""

from langchain_core.output_parsers import StrOutputParser

from llm import get_llm
from prompts.sql_prompt import SQL_GENERATION_PROMPT, BUSINESS_SUMMARY_PROMPT
from tools.tool_registry import get_tool_registry
from schema_cache import get_schema_cache, load_schema_cache
from schema_formatter import format_schema
from sql_validator import validate_sql
from sql_repair import repair_sql
from chart_builder import build_chart_from_df
from state import CopilotState
from logger import get_logger

log = get_logger("sql_agent")

MAX_REPAIR_ATTEMPTS = 3


def _get_schema_text() -> str:
    """Return the formatted schema string from cache, loading if necessary."""
    metadata = get_schema_cache()
    if metadata is None:
        log.warning("Schema cache empty — loading now.")
        metadata = load_schema_cache()
    return format_schema(metadata)


def _execute_sql(sql_tool, query: str) -> dict:
    """Execute SQL and return the tool result dict."""
    return sql_tool.execute(query)


def run_sql_agent(state: CopilotState) -> CopilotState:
    """Run the full SQL generation → validation → execution → repair pipeline."""
    log.info("Starting SQL Agent pipeline...")
    question = state.get("question", "")

    if not question:
        state["error"] = "No question provided to SQL agent."
        state["business_summary"] = "I didn't receive a question. Please try again."
        return state

    llm = get_llm()
    sql_tool = get_tool_registry().get_tool("sql_tool")

    if not sql_tool:
        state["error"] = "SQL Tool not found in registry."
        state["business_summary"] = "Internal error: SQL Tool is unavailable."
        return state

    # ── Step 1: Load Schema ────────────────────────────────────────────────────
    schema_text = _get_schema_text()
    metadata = get_schema_cache()

    # ── Step 2: Generate SQL ───────────────────────────────────────────────────
    log.info("Generating SQL for: %s", question[:80])
    sql_chain = SQL_GENERATION_PROMPT | llm | StrOutputParser()
    generated_sql = sql_chain.invoke({"schema": schema_text, "question": question})
    generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
    state["sql_query"] = generated_sql
    log.info("Generated SQL: %s", generated_sql[:200])

    # ── Step 3: Pre-execution Validation ──────────────────────────────────────
    if metadata:
        is_valid, validation_error = validate_sql(generated_sql, metadata)
        if not is_valid:
            log.warning("SQL validation failed: %s", validation_error)
            # Attempt a repair immediately using the validation error as the db_error
            generated_sql = repair_sql(generated_sql, validation_error, schema_text)
            generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
            state["sql_query"] = generated_sql
            log.info("SQL repaired after validation failure.")

    # ── Step 4: Execute with Auto-Repair Loop ─────────────────────────────────
    current_sql = generated_sql
    tool_result = _execute_sql(sql_tool, current_sql)

    attempt = 0
    while tool_result["error"] and attempt < MAX_REPAIR_ATTEMPTS:
        attempt += 1
        db_error = tool_result["error"]
        log.warning(
            "SQL execution failed (attempt %d/%d): %s",
            attempt, MAX_REPAIR_ATTEMPTS, db_error,
        )

        repaired_sql = repair_sql(current_sql, db_error, schema_text)
        repaired_sql = repaired_sql.replace("```sql", "").replace("```", "").strip()

        if repaired_sql == current_sql:
            log.warning("LLM returned identical SQL — stopping repair loop early.")
            break

        current_sql = repaired_sql
        state["sql_query"] = current_sql
        log.info("Repair attempt %d SQL: %s", attempt, current_sql[:200])
        tool_result = _execute_sql(sql_tool, current_sql)

    # ── Step 5: Handle Final Failure ──────────────────────────────────────────
    if tool_result["error"]:
        log.error("SQL pipeline failed after %d repair attempt(s).", attempt)
        state["error"] = tool_result["error"]
        state["business_summary"] = (
            "I was unable to retrieve the data needed to answer your question. "
            "This may be because the question requires data or relationships that are "
            "not currently available in the database. "
            "Please try rephrasing your question or ask about a different metric."
        )
        return state

    # ── Step 6: Process Results ────────────────────────────────────────────────
    df = tool_result["df"]

    if df is None or df.empty:
        log.info("SQL query returned no results.")
        state["business_summary"] = (
            "The query ran successfully, but no data matched your criteria. "
            "Try adjusting the filters or broadening your question."
        )
        state["sql_result"] = []
        return state

    state["sql_result"] = df.to_dict(orient="records")
    state["execution_time"] = tool_result.get("execution_time", 0.0)

    # ── Step 7: Generate Business Summary ─────────────────────────────────────
    log.info("Generating business summary for %d rows...", len(df))

    if len(df) <= 30:
        df_text = df.to_string(index=False)
    else:
        df_text = (
            df.head(20).to_string(index=False)
            + "\n\n... (middle rows omitted) ...\n\n"
            + df.tail(10).to_string(index=False, header=False)
        )

    summary_chain = BUSINESS_SUMMARY_PROMPT | llm | StrOutputParser()
    summary = summary_chain.invoke({"question": question, "dataframe_text": df_text})
    state["business_summary"] = summary.strip()
    log.info("SQL Agent pipeline completed successfully.")

    # ── Step 8: Build Chart + Table + Insight (optional, never raises) ────────
    chart_result = build_chart_from_df(df, question)
    if chart_result:
        state["chart_data"]    = chart_result["chart_json"]
        state["table_data"]    = chart_result["table_rows"]
        state["chart_insight"] = chart_result["insight"]
        log.info("Chart built for SQL result (%d rows).", len(df))

    return state
