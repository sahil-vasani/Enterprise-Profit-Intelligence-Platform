"""
config.py — Central configuration for the AI Business Copilot.
Reads settings from .env and exposes them as module-level constants.
"""

from pathlib import Path

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── Project Metadata ─────────────────────────────────────────────────────────
PROJECT_NAME = "Enterprise Profit Intelligence Platform"
PROJECT_VERSION = "1.0.0"
PROJECT_AUTHOR = "Analytics Team"

# ── Directory Paths ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
REPORT_DIR = PROJECT_ROOT / "reports"
LOG_DIR = PROJECT_ROOT / "logs" / "copilot"
ANALYTICS_DIR = PROJECT_ROOT / "src" / "analytics"
ML_DIR = PROJECT_ROOT / "src" / "ml"

# ── Ollama Configuration ─────────────────────────────────────────────────────
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))

# ── Database Configuration ───────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/enterprise_dw"
)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── General ───────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
MEMORY_WINDOW_SIZE = 10  # Number of recent conversation turns to keep
