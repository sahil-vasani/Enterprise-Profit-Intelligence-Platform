<div align="center">

<h1>🏢 Enterprise Profit Intelligence Platform</h1>
<p><strong>A production-grade, end-to-end Business Intelligence system combining a PostgreSQL Data Warehouse, Power BI Dashboards, and a LangGraph-powered AI Copilot — all running 100% locally.</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/PostgreSQL-Data_Warehouse-336791?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/LangGraph-AI_Agents-FF6B35?style=for-the-badge&logo=langchain&logoColor=white"/>
  <img src="https://img.shields.io/badge/Ollama-Qwen2.5--7B-black?style=for-the-badge&logo=ollama&logoColor=white"/>
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Power_BI-Dashboards-F2C811?style=for-the-badge&logo=powerbi&logoColor=black"/>
</p>

</div>

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [System Architecture](#-system-architecture)
- [Data Engineering Pipeline](#-data-engineering-pipeline)
- [AI Copilot — Four Agents](#-ai-copilot--four-agents)
- [Power BI Dashboards](#-power-bi-dashboards)
- [Folder Structure](#-folder-structure)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Example Queries](#-example-queries)
- [Machine Learning](#-machine-learning)
- [Future Roadmap](#-future-roadmap)
- [Screenshots](#-screenshots)

---

## 🌟 Project Overview

This project is a **complete, real-world Business Intelligence portfolio** built around the Amazon Sales Dataset from Kaggle. Because the raw dataset lacked enterprise-grade attributes, additional **synthetic business data** was generated and merged — covering customers, marketing campaigns, inventory, warehouses, logistics, returns, and finance metrics.

The final unified dataset was loaded into a proper **PostgreSQL Data Warehouse** using a **Star Schema** design, then exposed through:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Data Warehouse** | PostgreSQL + Star Schema | Persistent, queryable business data |
| **BI Dashboards** | Power BI (`.pbix`) | Executive and departmental reporting |
| **AI Copilot** | LangGraph + Qwen2.5-7B | Natural language analytics + SQL + Predictions |
| **Web UI** | Streamlit + Plotly | Interactive browser-based interface |
| **ML Models** | Scikit-Learn Random Forest | Profit & revenue forecasting |

> **Key differentiator**: The AI Copilot uses **dynamic schema introspection** — it reads the actual PostgreSQL schema at runtime instead of relying on hardcoded table definitions. This means the AI will never generate invalid SQL due to a schema mismatch.

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Interface Layer                        │
│              Streamlit Web App  ·  Power BI Desktop             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   LangGraph AI Engine                           │
│                                                                 │
│  ┌──────────┐  ┌─────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ SQL Agent│  │ Analytics   │  │Prediction │  │  Report   │  │
│  │          │  │ Agent       │  │Agent      │  │  Agent    │  │
│  └────┬─────┘  └──────┬──────┘  └─────┬─────┘  └─────┬─────┘  │
│       └───────────────┴───────────────┴───────────────┘        │
│                               │                                 │
│                    Ollama · Qwen2.5-7B                          │
│              (Local LLM — no cloud API required)                │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   Data & Model Layer                            │
│                                                                 │
│  PostgreSQL Data Warehouse        Scikit-Learn ML Models        │
│  ┌──────────────────────────┐   ┌───────────────────────────┐   │
│  │ analytics schema         │   │ best_model.pkl (28.5 MB)  │   │
│  │ ├── fact_sales           │   │ feature_columns.pkl       │   │
│  │ ├── dim_product          │   │ column_medians.pkl        │   │
│  │ ├── dim_customer         │   └───────────────────────────┘   │
│  │ ├── dim_date             │                                   │
│  │ ├── dim_location         │   Dynamic Schema Loader           │
│  │ ├── dim_marketing        │   (Reads information_schema —     │
│  │ ├── dim_inventory        │    no hardcoded table list)       │
│  │ ├── dim_returns          │                                   │
│  │ └── vw_sales_reporting   │                                   │
│  └──────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Engineering Pipeline

```
Amazon Sales CSV (Kaggle)
        │
        ▼
Synthetic Data Generation
(customers, campaigns, inventory,
 logistics, returns, finance metrics)
        │
        ▼
Final Merged Enterprise Dataset
        │
        ▼
PostgreSQL Staging Table  (stg_amazon_sales_raw)
        │
        ▼  ETL Transform & Clean
Star Schema Data Warehouse
   fact_sales ─── dim_product
       │       ├── dim_customer
       │       ├── dim_date
       │       ├── dim_location
       │       ├── dim_marketing
       │       ├── dim_inventory
       │       └── dim_returns
        │
        ▼
   Power BI  ·  AI Copilot  ·  ML Models
```

**Data Warehouse facts:**
- **128,975** sales transactions across **4 months** (Mar–Jun 2022)
- **29,671** unique customers across multiple segments
- **235 columns** across 12 dimension and fact tables
- **7 foreign-key relationships** enforced in the star schema

---

## 🤖 AI Copilot — Four Agents

The Copilot uses a **LangGraph StateGraph** as an intent router. When the user submits a question, the LLM classifies the intent and routes it to the correct specialist agent.

### 1. 🗄️ SQL Agent
- Loads the live schema from `information_schema` at startup via `schema_loader.py`
- Builds a context-aware schema string (tables, columns, data types, foreign keys)
- Generates SQL, **validates** it against the real schema before execution
- Auto-repairs common SQL errors via `sql_repair.py`
- Passes results to `chart_builder.py` which auto-selects chart type (bar / line / pie / KPI callout)

### 2. 📊 Analytics Agent
- Invokes 7 specialist Python modules — no LLM-generated SQL risk
- Each module performs pre-coded, domain-specific aggregations against the data warehouse
- Modules: `profit_analysis` · `customer_analysis` · `inventory_analysis` · `marketing_analysis` · `returns_analysis` · `product_analysis` · `statistical_analysis`

### 3. 🔮 Prediction Agent
- Loads pre-trained **Random Forest** (`best_model.pkl`, 28.5 MB) via `joblib`
- Extracts prediction target and time horizon from the natural language query
- Builds a feature set from median values in `fact_sales` for zero-shot inference
- Returns a confidence-backed forecast — entirely local, no external API call

### 4. 📝 Report Agent
- Composes a structured executive report in Markdown
- Pulls live KPIs from `fact_sales` (revenue, profit, margin %, order count)
- Formats the output as a multi-section business narrative ready for stakeholders

---

## 📊 Power BI Dashboards

The project includes a fully designed **Power BI report** (`powerBI dashboard/Enterprise_Profit_Intelligence.pbix`) with **8 dedicated dashboards** connected to the PostgreSQL data warehouse.

| # | Dashboard | Key Metrics Covered |
|---|-----------|-------------------|
| 1 | **Executive Dashboard** | Total Revenue, Net Profit, Margin %, Orders, YoY comparison |
| 2 | **Sales Dashboard** | Revenue trends, order volumes, fulfilment performance by channel |
| 3 | **Customer Dashboard** | Segments, loyalty scores, CLV, repeat purchase rate |
| 4 | **Product Dashboard** | Category performance, SKU profitability, ABC classification |
| 5 | **Inventory Dashboard** | Turnover ratio, stockout risk, dead stock, reorder alerts |
| 6 | **Marketing Dashboard** | Campaign ROI, acquisition costs, channel attribution |
| 7 | **Returns & Logistics Dashboard** | Return rates by reason, refund volumes, courier performance |
| 8 | **Enterprise Analysis Center** | Cross-functional KPIs with drill-through capability |

> 📁 **File**: `powerBI dashboard/Enterprise_Profit_Intelligence.pbix` — Open in Power BI Desktop and connect to your local PostgreSQL instance.

---

## 📂 Folder Structure

```
Enterprise-Profit-Intelligence-Platform/
│
├── run_project.py              # Production launcher (health check → Streamlit)
├── health_check.py             # 12-stage system validator
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
│
├── powerBI dashboard/
│   ├── Enterprise_Profit_Intelligence.pbix   # Power BI report (8 dashboards)
│   └── images/                               # Dashboard screenshot exports
│
├── data/                       # Raw & processed datasets
│
├── models/                     # Pre-trained ML model artefacts
│   ├── best_model.pkl          # Random Forest (28.5 MB)
│   ├── feature_columns.pkl     # Training feature column list
│   └── column_medians.pkl      # Median feature values for inference
│
├── docs/
│   └── Images/                 # App UI screenshots
│
├── logs/                       # Runtime application logs
├── reports/                    # Generated AI report outputs
├── figures/                    # EDA & training figures
│
└── src/
    ├── analytics/              # Specialist analytical modules
    │   ├── profit_analysis.py
    │   ├── customer_analysis.py
    │   ├── inventory_analysis.py
    │   ├── marketing_analysis.py
    │   ├── returns_analysis.py
    │   ├── product_analysis.py
    │   └── statistical_analysis.py
    │
    ├── copilot/                # AI Backend — LangGraph engine
    │   ├── agents/             # SQL · Analytics · Prediction · Report agents
    │   ├── prompts/            # Agent system prompts
    │   ├── tools/              # LangChain tool wrappers
    │   ├── graph.py            # LangGraph StateGraph router
    │   ├── chart_builder.py    # Auto chart selection (bar/line/pie/KPI)
    │   ├── schema_loader.py    # Live PostgreSQL schema introspection
    │   ├── schema_cache.py     # In-memory schema cache
    │   ├── schema_formatter.py # Schema → LLM prompt formatter
    │   ├── sql_validator.py    # Pre-execution SQL validation
    │   ├── sql_repair.py       # Auto SQL error correction
    │   ├── database.py         # SQLAlchemy engine & connection pool
    │   ├── llm.py              # Ollama client setup
    │   ├── router.py           # Intent classification logic
    │   └── state.py            # LangGraph CopilotState definition
    │
    ├── ml/                     # Model training scripts
    ├── business_enrichment/    # Synthetic data generation scripts
    ├── data_quality/           # Data validation & cleaning
    ├── services/               # Shared service utilities
    │
    └── ui/                     # Streamlit frontend
        ├── app.py              # Entry point & page router
        ├── components.py       # Chat UI · AI response renderer
        ├── sidebar.py          # Navigation · status cards
        ├── charts.py           # Plotly chart configurations
        ├── session.py          # st.session_state management
        └── styles.py           # CSS injection & theme
```

---

## 🛠 Tech Stack

| Category | Technology | Notes |
|----------|-----------|-------|
| **Language** | Python 3.11+ | Core runtime |
| **AI Framework** | LangChain + LangGraph | Agent orchestration & intent routing |
| **Local LLM** | Ollama · Qwen2.5-7B | 100% local — no OpenAI API required |
| **Database** | PostgreSQL | Star Schema data warehouse |
| **ORM / SQL** | SQLAlchemy + psycopg2 | Connection pooling & query execution |
| **Machine Learning** | Scikit-Learn | Random Forest forecasting model |
| **Data Processing** | Pandas + NumPy | ETL, feature engineering |
| **Frontend** | Streamlit 1.51 | Browser-based web UI |
| **Charts** | Plotly Express | Interactive visualisations |
| **BI Reporting** | Power BI Desktop | `.pbix` dashboards (8 pages) |
| **Env Management** | python-dotenv | Secrets & config isolation |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL running locally (with the `enterprise_profit_intelligence` database)
- [Ollama](https://ollama.ai) installed

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/enterprise-profit-intelligence-platform.git
cd enterprise-profit-intelligence-platform
```

### 2. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` with your values:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/enterprise_profit_intelligence
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Pull the LLM Model
```bash
ollama pull qwen2.5:7b
```

### 5. Launch the Platform
```bash
python run_project.py
```

The launcher runs a **12-stage health check** first, then opens Streamlit at `http://localhost:8501`.

| Health Check Stage | What It Validates |
|--------------------|-------------------|
| Python | Version 3.11+ confirmed |
| Project Structure | All 9 required directories present |
| Environment | `.env` variables loaded |
| Packages | 10 key packages importable |
| Database | PostgreSQL connection successful |
| Ollama | LLM model reachable and responding |
| Database Metadata | Schema introspection (12 tables, 235 columns) |
| ML Models | `best_model.pkl` + supporting files present |
| Analytics | 7 analytics modules importable |
| AI Agents | 4 LangGraph agents importable |
| LangGraph | StateGraph compiles successfully |
| Streamlit | `app.py` entry point found |

> **Note**: A `WARN` on the Ollama stage (e.g., model still loading) does **not** block launch — the app starts with a warning and the LLM becomes available within seconds.

---

## 💬 Example Queries

| Query | Agent Routed To | Output Produced |
|-------|----------------|-----------------|
| *"Top 10 profitable products"* | SQL Agent | Horizontal bar chart + ranked table |
| *"Revenue by category"* | SQL Agent | Bar chart — Set ($39M) leads |
| *"Monthly revenue trend"* | SQL Agent | Line chart, chronologically sorted |
| *"Who are my best customers?"* | SQL Agent | Table by segment + revenue |
| *"Run profit analysis"* | Analytics Agent | Full profit module output |
| *"Show returns by reason"* | Analytics Agent | Return count + refund totals |
| *"Predict next month profit"* | Prediction Agent | Random Forest point forecast |
| *"Generate CEO report"* | Report Agent | Multi-section executive narrative |

---

## 🧠 Machine Learning

The **Prediction Agent** uses a pre-trained Random Forest model built on the `fact_sales` table:

- **Input**: Natural language query (e.g., *"predict next month revenue"*)
- **Feature extraction**: Target metric + time horizon parsed from the query
- **Inference**: Median feature values from `fact_sales` used as baseline input vector
- **Output**: Point forecast with confidence bounds
- **Model size**: 28.5 MB — loaded once at startup via `joblib`, no reload on query
- **Privacy**: All inference runs locally — no data leaves the machine

---

## 🔮 Future Roadmap

- [ ] **Streaming responses** — Token-level streaming from Ollama through LangGraph to the UI
- [ ] **Multi-turn memory** — Persistent conversation history across sessions via PostgreSQL
- [ ] **Guardrails** — SQL injection prevention and stricter schema-aware query validation
- [ ] **Dockerization** — `docker-compose.yml` bundling PostgreSQL, Ollama, and Streamlit
- [ ] **Scheduled reports** — Cron-triggered automated PDF/Markdown report generation
- [ ] **Prediction charts** — Historical + forecast trend line chart rendered in the UI

---

## 📄 License

This project is built for portfolio and educational purposes.

---

## 📸 Screenshots

### AI Copilot — Web Interface

**Landing page** — greeting, 8 one-click suggestion pills, live model status in sidebar, and chat input.

![AI Copilot Landing Page](docs/Images/01_ai_copilot_landing.png)

---

**AI response with chart** — "Top 10 profitable products" routed to the SQL Agent, returning an executive insight summary and an interactive Plotly horizontal bar chart.

![AI Response with Chart](docs/Images/02_ai_response_with_chart.png)

---

### Power BI Dashboards

**Executive Dashboard** — Revenue, net profit, margin %, and order volume at a glance.

![Executive Dashboard](powerBI%20dashboard/images/Executive%20Dashboard.png)

---

**Sales Dashboard** — Revenue trends, order volumes, and fulfilment channel performance.

![Sales Dashboard](powerBI%20dashboard/images/Sales%20Dashboard.png)

---

**Customer Dashboard** — Customer segmentation, loyalty scores, CLV, and repeat purchase analysis.

![Customer Dashboard](powerBI%20dashboard/images/Customer%20Dashboard.png)

---

<div align="center">
  <p>Built with ❤️ using PostgreSQL · LangGraph · Ollama · Streamlit · Power BI</p>
  <p><em>Enterprise Profit Intelligence Platform — Local-First Business AI</em></p>
</div>
