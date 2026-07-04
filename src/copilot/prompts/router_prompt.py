"""
router_prompt.py — Intent classification prompt for the AI Business Copilot.
"""

ROUTER_PROMPT = """Classify the following user question into exactly ONE category.

CATEGORIES:
- sql: Questions that need data retrieval from the database (e.g., revenue, orders, top products, customer counts, warehouse performance).
- analytics: Questions about business analysis, trends, comparisons, or explanations (e.g., why is profit declining, customer segmentation analysis).
- prediction: Questions about forecasting or predicting future metrics (e.g., predict next month's profit, forecast revenue).
- report: Requests for comprehensive reports or summaries (e.g., generate CEO report, monthly summary, executive briefing).
- general: Greetings, general knowledge, or questions not related to business data.

EXAMPLES:
User: "Top 10 profitable products" → sql
User: "Total revenue by category" → sql
User: "Which warehouse is losing money?" → sql
User: "Show me customer distribution by state" → sql
User: "Why is profit decreasing?" → analytics
User: "Compare marketing campaigns" → analytics
User: "What drives customer returns?" → analytics
User: "Analyse inventory turnover by category" → analytics
User: "Predict next month's profit" → prediction
User: "Forecast revenue for Q3" → prediction
User: "What will be the estimated net profit?" → prediction
User: "Generate CEO report" → report
User: "Monthly executive summary" → report
User: "Create a business performance overview" → report
User: "Hello" → general
User: "What can you do?" → general
User: "Thanks" → general

Respond with ONLY the category label (sql, analytics, prediction, report, or general).
No explanation. No punctuation. Just the label.

User Question: {question}
Category:"""
