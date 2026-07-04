import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit as st

@st.cache_data(ttl=300)
def get_df(sql: str, fallback_df: pd.DataFrame) -> pd.DataFrame:
    from services.database_service import get_df as db_get_df
    return db_get_df(sql, fallback_df)

def get_chart_config():
    return {'displayModeBar': True, 'scrollZoom': True, 'displaylogo': False}

@st.cache_data(ttl=300)
def create_revenue_trend_chart():
    """Returns a Plotly line chart for Revenue Trend."""
    dates = pd.date_range(start='2023-01-01', periods=12, freq='ME')
    revenue = [120, 135, 125, 145, 160, 155, 170, 190, 185, 210, 230, 250]
    fallback = pd.DataFrame({'Date': dates, 'Revenue ($k)': revenue})
    
    sql = "SELECT DATE_TRUNC('month', order_date) as \"Date\", SUM(total_amount)/1000 as \"Revenue ($k)\" FROM fact_sales GROUP BY 1 ORDER BY 1 LIMIT 12"
    df = get_df(sql, fallback)
    
    fig = px.line(df, x='Date', y='Revenue ($k)', title="Revenue Trend (YTD)", markers=True)
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
    fig.update_traces(line_color='#2563eb', line_width=3, hovertemplate='<b>%{x}</b><br>Revenue: $%{y}k<extra></extra>')
    return fig

@st.cache_data(ttl=300)
def create_category_distribution_chart():
    """Returns a Plotly pie chart for Category Distribution."""
    categories = ['Electronics', 'Apparel', 'Home Goods', 'Software', 'Services']
    values = [45, 25, 15, 10, 5]
    fallback = pd.DataFrame({'Category': categories, 'Revenue': values})
    
    sql = "SELECT p.category as \"Category\", sum(s.total_amount) as \"Revenue\" FROM fact_sales s JOIN dim_product p ON s.product_id = p.product_id GROUP BY 1"
    df = get_df(sql, fallback)
    
    fig = px.pie(df, values='Revenue', names='Category', hole=0.4, title="Revenue by Category")
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)")
    fig.update_traces(hovertemplate='<b>%{label}</b><br>Revenue: $%{value:,.0f}<br>Share: %{percent}<extra></extra>')
    return fig

@st.cache_data(ttl=300)
def create_monthly_profit_chart():
    """Returns a Plotly bar chart for Monthly Profit."""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    profit = [42, 48, 51, 46, 59, 65]
    fallback = pd.DataFrame({'Month': months, 'Profit ($k)': profit})
    
    sql = "SELECT TO_CHAR(order_date, 'Mon') as \"Month\", sum(net_profit)/1000 as \"Profit ($k)\" FROM fact_sales GROUP BY TO_CHAR(order_date, 'Mon'), DATE_PART('month', order_date) ORDER BY DATE_PART('month', order_date) LIMIT 6"
    df = get_df(sql, fallback)
    
    fig = px.bar(df, x='Month', y='Profit ($k)', title="Monthly Net Profit", text='Profit ($k)')
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
    fig.update_traces(marker_color='#10b981', textposition='outside', texttemplate='$%{text}k', hovertemplate='<b>%{x}</b><br>Profit: $%{y}k<extra></extra>')
    return fig

@st.cache_data(ttl=300)
def create_customer_segmentation_chart():
    """Returns a Plotly scatter chart for Customer Segmentation."""
    np.random.seed(42)
    recency = np.random.randint(1, 100, 50)
    frequency = np.random.randint(1, 50, 50)
    monetary = np.random.randint(100, 5000, 50)
    fallback = pd.DataFrame({'Recency (Days)': recency, 'Frequency (Orders)': frequency, 'Monetary': monetary})
    
    sql = "SELECT CURRENT_DATE - MAX(order_date) as \"Recency (Days)\", COUNT(order_id) as \"Frequency (Orders)\", SUM(total_amount) as \"Monetary\" FROM fact_sales GROUP BY customer_id LIMIT 50"
    df = get_df(sql, fallback)
    
    fig = px.scatter(
        df, x='Recency (Days)', y='Frequency (Orders)', size='Monetary', 
        title="Customer Segmentation (RFM)",
    )
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_traces(marker=dict(color='#8b5cf6', opacity=0.7), hovertemplate='Recency: %{x} days<br>Frequency: %{y} orders<br>Value: $%{marker.size:,.0f}<extra></extra>')
    return fig
