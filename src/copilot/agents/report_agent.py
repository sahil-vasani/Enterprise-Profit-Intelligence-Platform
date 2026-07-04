"""
report_agent.py — Agent for generating executive reports.
"""

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm import get_llm
from state import CopilotState
from logger import get_logger
from agents.sql_agent import run_sql_agent
from agents.analytics_agent import run_analytics_agent
import copy

log = get_logger("report_agent")

_REPORT_PROMPT = """You are a Chief of Staff AI.
You have been asked to generate a business report: "{question}"

You have gathered the following insights:
SQL Insights: {sql_summary}
Analytics Insights: {analytics_summary}

Please generate a professional, clean, and structured executive report based on this information.
Include an Executive Summary, Key Findings, and Next Steps.

Report:
"""

_REPORT_TEMPLATES = {
    "CEO Report": {
        "sql": "Total revenue and net profit by quarter",
        "analytics": "profit analysis"
    },
    "Sales Report": {
        "sql": "Top 10 products by revenue",
        "analytics": "product analysis"
    },
    "Marketing Report": {
        "sql": "Total marketing cost and campaign ROI",
        "analytics": "marketing analysis"
    },
    "Inventory Report": {
        "sql": "Current inventory cost and stockout probability",
        "analytics": "inventory analysis"
    },
    "Customer Report": {
        "sql": "Top customers by revenue",
        "analytics": "customer analysis"
    },
    "Returns Report": {
        "sql": "Total refund amount and top returned products",
        "analytics": "returns analysis"
    },
    "Executive Summary": {
        "sql": "Total revenue, net profit, and profit margin",
        "analytics": "profit analysis"
    }
}

def run_report_agent(state: CopilotState) -> CopilotState:
    """Generate an executive report by aggregating data from other agents."""
    log.info("Starting Report Agent pipeline...")
    question = state.get("question", "")
    
    if not question:
        state["error"] = "No question provided to report agent."
        state["business_summary"] = "I didn't receive a question."
        return state

    # Match report type based on question keywords
    matched_type = "Executive Summary"
    for template_name in _REPORT_TEMPLATES:
        # Simple match: if any word in the template name is in the question (ignoring 'Report')
        keywords = template_name.lower().replace("report", "").strip().split()
        if any(kw in question.lower() for kw in keywords if kw):
            matched_type = template_name
            break

    template = _REPORT_TEMPLATES[matched_type]
    log.info(f"Matched Report Type: {matched_type}")

    try:
        # Run SQL pass
        sql_state = copy.deepcopy(state)
        sql_state["question"] = template["sql"]
        sql_state = run_sql_agent(sql_state)
        sql_summary = sql_state.get("business_summary", "No SQL data available.")

        # Run Analytics pass
        analytics_state = copy.deepcopy(state)
        analytics_state["question"] = template["analytics"]
        analytics_state = run_analytics_agent(analytics_state)
        analytics_summary = analytics_state.get("business_summary", "No Analytics data available.")

        # Generate Report
        llm = get_llm()
        prompt = PromptTemplate(
            input_variables=["question", "sql_summary", "analytics_summary"],
            template=_REPORT_PROMPT
        )
        chain = prompt | llm | StrOutputParser()
        
        report = chain.invoke({
            "question": question,
            "sql_summary": sql_summary,
            "analytics_summary": analytics_summary
        })
        
        state["business_summary"] = report.strip()

    except Exception as e:
        log.error("Error in Report Agent pipeline: %s", e)
        state["error"] = str(e)
        state["business_summary"] = "An error occurred while generating the report."

    return state
