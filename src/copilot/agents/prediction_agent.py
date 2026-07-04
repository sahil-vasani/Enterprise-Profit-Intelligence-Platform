"""
prediction_agent.py — Agent for generating business predictions using ML.
"""

from pathlib import Path
import joblib
import pandas as pd
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm import get_llm
from state import CopilotState
from logger import get_logger

log = get_logger("prediction_agent")

_model = None
_feature_cols = None
_medians = None

def _load_model():
    """Load the trained ML model and feature configuration once."""
    global _model, _feature_cols, _medians
    if _model is None:
        models_dir = Path(__file__).parent.parent.parent.parent / "models"
        model_path = models_dir / "best_model.pkl"
        features_path = models_dir / "feature_columns.pkl"
        medians_path = models_dir / "column_medians.pkl"
        
        try:
            _model = joblib.load(model_path)
            _feature_cols = joblib.load(features_path)
            _medians = joblib.load(medians_path)
            log.info("ML model and feature maps loaded successfully.")
        except Exception as e:
            log.error("Failed to load ML model: %s", e)
            raise e

_PREDICTION_PROMPT = """You are an AI Business Copilot.
The user asked a predictive question: "{question}"

Our machine learning model has generated a baseline prediction for this scenario:
Predicted Value: {prediction_value}

Your task is to respond to the user with:
1. The predicted value clearly stated.
2. A short explanation of what this means.
3. A strategic business recommendation.

Keep the response concise, professional, and easy to read. Do not show code.
Response:
"""

def _build_features(question: str, feature_cols: list, medians: dict) -> dict:
    """Prepare feature dictionary based on medians and simple question filters."""
    input_data = {}
    q = question.lower()
    
    # Initialize with medians
    for col in feature_cols:
        input_data[col] = medians.get(col, 0)
        
    # Apply simple business filters based on keywords
    if "electronics" in q and "Category" in feature_cols:
        input_data["Category"] = "Electronics"
    elif "apparel" in q and "Category" in feature_cols:
        input_data["Category"] = "Apparel"
        
    if "b2b" in q and "B2B" in feature_cols:
        input_data["B2B"] = 1
    elif "b2c" in q and "B2B" in feature_cols:
        input_data["B2B"] = 0
        
    # High discount assumption
    if "discount" in q and "sale" in q and "discount_cost" in feature_cols:
        input_data["discount_cost"] = medians.get("discount_cost", 0) * 1.5
        
    return input_data

def run_prediction_agent(state: CopilotState) -> CopilotState:
    """Generate a prediction and business summary."""
    log.info("Starting Prediction Agent pipeline...")
    question = state.get("question", "")
    
    if not question:
        state["error"] = "No question provided to prediction agent."
        state["business_summary"] = "I didn't receive a question."
        return state

    try:
        _load_model()
        
        # Build features
        input_data = _build_features(question, _feature_cols, _medians)
        df_input = pd.DataFrame([input_data])
        
        # Generate prediction
        prediction = _model.predict(df_input)[0]
        
        # Format the prediction value beautifully
        if "profit" in question.lower() or "revenue" in question.lower() or "value" in question.lower():
            pred_str = f"₹{prediction:,.2f}"
        else:
            pred_str = f"{prediction:,.2f}"
            
        # Summarize with LLM
        llm = get_llm()
        prompt = PromptTemplate(
            input_variables=["question", "prediction_value"],
            template=_PREDICTION_PROMPT
        )
        chain = prompt | llm | StrOutputParser()
        
        summary = chain.invoke({
            "question": question,
            "prediction_value": pred_str
        })
        
        state["business_summary"] = summary.strip()
        state["prediction_result"] = pred_str

    except Exception as e:
        log.error("Error in Prediction Agent pipeline: %s", e)
        state["error"] = str(e)
        state["business_summary"] = "An error occurred while generating the prediction."

    return state
