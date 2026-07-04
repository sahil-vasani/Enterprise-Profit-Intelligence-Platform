"""
graph.py — LangGraph workflow for the AI Business Copilot.
Defines the state graph with routing, placeholder nodes, and response formatting.
"""

import time

from langgraph.graph import END, StateGraph

from logger import get_logger
from router import classify_intent
from state import CopilotState
from utils import get_timestamp
from agents.sql_agent import run_sql_agent
from agents.analytics_agent import run_analytics_agent
from agents.prediction_agent import run_prediction_agent
from agents.report_agent import run_report_agent

log = get_logger("graph")


# ── Node Functions ────────────────────────────────────────────────────────────

def route_node(state: CopilotState) -> CopilotState:
    """Classify the user question and set the intent."""
    log.info("─── Route Node: started")
    start = time.perf_counter()

    question = state.get("question", "")
    intent = classify_intent(question)

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── Route Node: finished (%.3fs) → intent=%s", elapsed, intent)

    return {
        **state,
        "intent": intent,
        "timestamp": get_timestamp(),
        "error": "",
    }


def sql_node(state: CopilotState) -> CopilotState:
    """Execute the SQL Agent workflow to answer business questions."""
    log.info("─── SQL Node: started")
    start = time.perf_counter()

    # Call the actual agent pipeline
    updated_state = run_sql_agent(state)

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── SQL Node: finished (%.3fs)", elapsed)

    return updated_state


def analytics_node(state: CopilotState) -> CopilotState:
    """Execute the Analytics Agent workflow to generate business insights."""
    log.info("─── Analytics Node: started")
    start = time.perf_counter()

    updated_state = run_analytics_agent(state)

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── Analytics Node: finished (%.3fs)", elapsed)

    return updated_state


def prediction_node(state: CopilotState) -> CopilotState:
    """Execute the Prediction Agent workflow using the ML model."""
    log.info("─── Prediction Node: started")
    start = time.perf_counter()

    updated_state = run_prediction_agent(state)

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── Prediction Node: finished (%.3fs)", elapsed)

    return updated_state


def report_node(state: CopilotState) -> CopilotState:
    """Execute the Report Agent workflow to generate an executive report."""
    log.info("─── Report Node: started")
    start = time.perf_counter()

    updated_state = run_report_agent(state)

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── Report Node: finished (%.3fs)", elapsed)

    return updated_state


def general_node(state: CopilotState) -> CopilotState:
    """Answer general business questions conversationally using the LLM."""
    log.info("─── General Node: started")
    start = time.perf_counter()
    question = state.get("question", "")

    try:
        from llm import get_llm
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from prompts.system_prompt import SYSTEM_PROMPT

        llm = get_llm()
        prompt = PromptTemplate(
            input_variables=["system", "question"],
            template="{system}\n\nUser: {question}\nAssistant:",
        )
        chain = prompt | llm | StrOutputParser()
        answer = chain.invoke({"system": SYSTEM_PROMPT, "question": question})
        summary = answer.strip()
    except Exception as e:
        log.error("General node LLM call failed: %s", e)
        summary = (
            "I'm here to help with business questions about revenue, profit, "
            "customers, inventory, and forecasts. Could you rephrase your question?"
        )

    elapsed = round(time.perf_counter() - start, 3)
    log.info("─── General Node: finished (%.3fs)", elapsed)
    return {**state, "business_summary": summary}


def error_node(state: CopilotState) -> CopilotState:
    """Handle routing or processing errors gracefully."""
    log.error("─── Error Node: triggered")
    summary = (
        "I apologise, but I was unable to process your question. "
        "Please try rephrasing it or ask a different business question."
    )
    return {**state, "business_summary": summary, "error": "Routing failed."}


def response_node(state: CopilotState) -> CopilotState:
    """Format the final response for display."""
    log.info("─── Response Node: formatting output")
    return state


# ── Routing Logic ─────────────────────────────────────────────────────────────

def _route_by_intent(state: CopilotState) -> str:
    """Return the next node name based on the classified intent."""
    intent = state.get("intent", "general")
    valid_intents = {"sql", "analytics", "prediction", "report", "general"}
    if intent not in valid_intents:
        log.warning("Unknown intent '%s', routing to error.", intent)
        return "error_node"
    return f"{intent}_node"


# ── Graph Construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and compile the LangGraph workflow."""
    graph = StateGraph(CopilotState)

    # Add nodes
    graph.add_node("route_node", route_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("analytics_node", analytics_node)
    graph.add_node("prediction_node", prediction_node)
    graph.add_node("report_node", report_node)
    graph.add_node("general_node", general_node)
    graph.add_node("error_node", error_node)
    graph.add_node("response_node", response_node)

    # Entry point
    graph.set_entry_point("route_node")

    # Conditional routing from route_node
    graph.add_conditional_edges(
        "route_node",
        _route_by_intent,
        {
            "sql_node": "sql_node",
            "analytics_node": "analytics_node",
            "prediction_node": "prediction_node",
            "report_node": "report_node",
            "general_node": "general_node",
            "error_node": "error_node",
        }
    )

    # All workflow nodes → response_node → END
    for node in ["sql_node", "analytics_node", "prediction_node", "report_node", "general_node", "error_node"]:
        graph.add_edge(node, "response_node")

    graph.add_edge("response_node", END)

    log.info("LangGraph workflow compiled successfully.")
    return graph.compile()
