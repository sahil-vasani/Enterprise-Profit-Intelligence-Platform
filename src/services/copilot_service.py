"""
copilot_service.py - Abstraction layer for LangGraph AI workflow.
"""
import time
from copilot.graph import build_graph
from copilot.state import CopilotState
from copilot.utils import get_timestamp
from copilot.llm import get_llm
from copilot.config import OLLAMA_MODEL

_workflow = None

def _get_workflow():
    """Returns a singleton of the LangGraph workflow."""
    global _workflow
    if _workflow is None:
        _workflow = build_graph()
    return _workflow

def get_ai_status() -> dict:
    """Returns AI model connection status."""
    llm = get_llm()
    is_ready = llm._llm_type != "fallback"
    return {
        "ready": is_ready,
        "model": OLLAMA_MODEL
    }

def run_backend_query(question: str) -> dict:
    """Run a question through the cached LangGraph workflow."""
    workflow = _get_workflow()
    
    initial_state = {
        "question": question,
        "intent": "",
        "messages": [],
        "sql_query": "",
        "sql_result": [],
        "analytics_result": "",
        "prediction_result": "",
        "business_summary": "",
        "chart_path": "",
        "chart_data": "",
        "table_data": [],
        "chart_insight": "",
        "execution_time": 0.0,
        "error": "",
        "conversation_id": "",
        "timestamp": get_timestamp(),
    }
    
    start = time.perf_counter()
    result = workflow.invoke(initial_state)
    result["execution_time"] = round(time.perf_counter() - start, 2)
    return result
