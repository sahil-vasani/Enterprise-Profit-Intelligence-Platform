"""
app.py — CLI entry point for the AI Business Copilot.
Runs the LangGraph workflow interactively.
"""

import time
import sys

from graph import build_graph
from logger import get_logger
from schema_cache import load_schema_cache
from state import CopilotState
from utils import get_timestamp

log = get_logger("app")

# ── Constants ─────────────────────────────────────────────────────────────────
SEPARATOR = "=" * 60
WELCOME_MSG = """
╔══════════════════════════════════════════════════════════════╗
║       Enterprise AI Business Copilot v1.0                   ║
║       Profit Intelligence Platform                          ║
╠══════════════════════════════════════════════════════════════╣
║  Ask business questions in natural language.                 ║
║  Type 'exit' or 'quit' to stop.                             ║
║  Type 'clear' to reset conversation.                        ║
╚══════════════════════════════════════════════════════════════╝
"""


def run_query(workflow, question: str) -> dict:
    """Run a single question through the LangGraph workflow."""
    initial_state: CopilotState = {
        "question": question,
        "intent": "",
        "messages": [],
        "sql_query": "",
        "sql_result": [],
        "analytics_result": "",
        "prediction_result": "",
        "business_summary": "",
        "chart_path": "",
        "execution_time": 0.0,
        "error": "",
        "conversation_id": "",
        "timestamp": get_timestamp(),
    }

    start = time.perf_counter()
    result = workflow.invoke(initial_state)
    result["execution_time"] = round(time.perf_counter() - start, 2)

    return result


def display_result(result: dict) -> None:
    """Display the workflow result in a formatted way."""
    print(f"\n{SEPARATOR}")
    print(f"  Intent Detected : {result.get('intent', 'unknown')}")
    print(f"  Execution Time  : {result.get('execution_time', 0)}s")
    print(SEPARATOR)
    print(f"\n{result.get('business_summary', 'No output generated.')}\n")

    if result.get("error"):
        print(f"  ⚠ Error: {result['error']}")

    print(SEPARATOR)


def main() -> None:
    """Main interactive loop."""
    print(WELCOME_MSG)

    log.info("Building LangGraph workflow...")
    workflow = build_graph()

    log.info("Loading database schema cache...")
    load_schema_cache()

    log.info("Copilot ready. Waiting for user input.")

    while True:
        try:
            question = input("\n🔍 Your Question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            sys.exit(0)

        if not question:
            continue

        if question.lower() in ("exit", "quit"):
            print("\nGoodbye! 👋")
            break

        if question.lower() == "clear":
            print("Conversation cleared.\n")
            continue

        result = run_query(workflow, question)
        display_result(result)


if __name__ == "__main__":
    main()
