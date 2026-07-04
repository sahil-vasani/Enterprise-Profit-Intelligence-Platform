"""
health_check.py — Full system validation for the Enterprise Profit Intelligence Platform.
Runs 12 staged checks and prints a professional health report.
Never launches Streamlit. Only validates.
"""

import sys
import io
import time
import importlib
from pathlib import Path

# ── Encoding fix for Windows terminals ────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Path Setup ─────────────────────────────────────────────────────────────────
# All copilot modules use flat imports (e.g. `from database import ...`).
# COPILOT_DIR must be first so copilot/utils.py is found before analytics/utils.py.
ROOT = Path(__file__).resolve().parent
COPILOT_DIR = ROOT / "src" / "copilot"
SRC_DIR     = ROOT / "src"

if str(COPILOT_DIR) not in sys.path:
    sys.path.insert(0, str(COPILOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

# ── Colour Codes ───────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS_TAG = f"{GREEN}PASS{RESET}"
FAIL_TAG = f"{RED}FAIL{RESET}"
WARN_TAG = f"{YELLOW}WARN{RESET}"

SEP = "=" * 60


# ── Result Container ──────────────────────────────────────────────────────────

class StageResult:
    def __init__(self, name: str, status: str, detail: str = "",
                 file_ref: str = "", suggested_fix: str = "", elapsed: float = 0.0):
        self.name        = name
        self.status      = status   # "PASS" | "FAIL" | "WARN"
        self.detail      = detail
        self.file_ref    = file_ref
        self.suggested_fix = suggested_fix
        self.elapsed     = elapsed

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def tag(self) -> str:
        return {"PASS": PASS_TAG, "FAIL": FAIL_TAG, "WARN": WARN_TAG}.get(self.status, WARN_TAG)


def _time_stage(fn) -> tuple:
    start = time.perf_counter()
    result = fn()
    return result, round(time.perf_counter() - start, 3)


def _print_stage(label: str, result: StageResult):
    print(f"  {label:<28} {result.tag()}  ({result.elapsed:.3f}s)")
    if result.detail:
        for line in result.detail.splitlines():
            print(f"       >> {line}")


# ── Stage 1 — Python Version ──────────────────────────────────────────────────

def run_stage1() -> StageResult:
    def check():
        major, minor = sys.version_info.major, sys.version_info.minor
        version_str = f"Python {major}.{minor}.{sys.version_info.micro}"
        if (major, minor) < (3, 11):
            return StageResult(
                "Python Version", "FAIL",
                detail=f"Found {version_str}. Minimum required: Python 3.11.",
                suggested_fix="Install Python 3.11 or higher from https://python.org",
            )
        return StageResult("Python Version", "PASS", detail=version_str)

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 2 — Project Structure ───────────────────────────────────────────────

def run_stage2() -> StageResult:
    def check():
        required = [
            ROOT / "src",
            ROOT / "src" / "copilot",
            ROOT / "src" / "ui",
            ROOT / "src" / "analytics",
            ROOT / "src" / "ml",
            ROOT / "models",
            ROOT / "reports",
            ROOT / "logs",
            ROOT / "data",
        ]
        missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
        if missing:
            return StageResult(
                "Project Structure", "FAIL",
                detail="Missing directories:\n" + "\n".join(f"  {m}" for m in missing),
                suggested_fix="Create the missing directories or re-clone the repository.",
            )
        return StageResult("Project Structure", "PASS", detail=f"{len(required)} directories verified")

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 3 — Environment Variables ──────────────────────────────────────────

def run_stage3() -> StageResult:
    def check():
        from dotenv import load_dotenv
        import os
        load_dotenv(ROOT / ".env")
        required_vars = ["DATABASE_URL", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "LOG_LEVEL"]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            return StageResult(
                "Environment Variables", "FAIL",
                detail="Missing variables:\n" + "\n".join(f"  {v}" for v in missing),
                file_ref=".env",
                suggested_fix="Add the missing variables to your .env file.",
            )
        return StageResult("Environment Variables", "PASS", detail=f"{len(required_vars)} variables present")

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 4 — Required Packages ──────────────────────────────────────────────

_PACKAGE_IMPORT_MAP = {
    "langchain":          "langchain",
    "langgraph":          "langgraph",
    "langchain-ollama":   "langchain_ollama",
    "langchain-community":"langchain_community",
    "ollama":             "ollama",
    "sqlalchemy":         "sqlalchemy",
    "psycopg2-binary":    "psycopg2",
    "python-dotenv":      "dotenv",
    "pandas":             "pandas",
    "numpy":              "numpy",
    "joblib":             "joblib",
    "pydantic":           "pydantic",
    "streamlit":          "streamlit",
    "plotly":             "plotly",
    "typing_extensions":  "typing_extensions",
    "psutil":             "psutil",
    "scikit-learn":       "sklearn",
}


def run_stage4() -> StageResult:
    def check():
        req_file = COPILOT_DIR / "requirements.txt"
        if not req_file.exists():
            req_file = ROOT / "requirements.txt"

        packages = [
            line.strip().split("==")[0].split(">=")[0].split("<=")[0]
            for line in req_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

        missing = []
        for pkg in packages:
            import_name = _PACKAGE_IMPORT_MAP.get(pkg, pkg.replace("-", "_"))
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing.append(pkg)

        if missing:
            return StageResult(
                "Required Packages", "FAIL",
                detail="Missing packages:\n" + "\n".join(f"  {p}" for p in missing),
                suggested_fix=f"Run: pip install {' '.join(missing)}",
            )
        return StageResult("Required Packages", "PASS", detail=f"{len(packages)} packages verified")

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 5 — Database ────────────────────────────────────────────────────────

def run_stage5() -> StageResult:
    def check():
        # Flat import — works because COPILOT_DIR is first on sys.path
        from src.copilot.database import test_connection
        ok = test_connection()
        if not ok:
            return StageResult(
                "Database", "FAIL",
                detail="Could not connect to PostgreSQL.",
                file_ref="src/copilot/database.py",
                suggested_fix="Verify DATABASE_URL in .env. Ensure PostgreSQL is running.",
            )
        return StageResult("Database", "PASS", detail="PostgreSQL connection successful")

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 6 — Ollama ──────────────────────────────────────────────────────────

def run_stage6() -> StageResult:
    def check():
        import os
        import requests
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model    = os.getenv("OLLAMA_MODEL",    "qwen2.5:7b")

        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                raise ConnectionError(f"Ollama server returned HTTP {resp.status_code}")
        except Exception as e:
            return StageResult(
                "Ollama", "FAIL",
                detail=f"Ollama server unreachable at {base_url}: {e}",
                file_ref="src/copilot/llm.py",
                suggested_fix="Start Ollama with: ollama serve",
            )

        available = [m.get("name", "") for m in resp.json().get("models", [])]
        if not any(model in a for a in available):
            return StageResult(
                "Ollama", "FAIL",
                detail=f"Model '{model}' not found. Available: {available or 'none'}",
                file_ref="src/copilot/llm.py",
                suggested_fix=f"Pull the model with: ollama pull {model}",
            )

        try:
            probe = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": "Hello", "stream": False},
                timeout=30,
            )
            data = probe.json()
            # Ollama returns "response" for non-streaming, "done" flag is always present
            has_content = bool(data.get("response")) or data.get("done") is not None
            if probe.status_code != 200 or not has_content:
                raise ValueError(f"Unexpected probe response: {data}")
        except Exception as e:
            return StageResult(
                "Ollama", "WARN",
                detail=f"Model reachable but probe failed: {e}",
                file_ref="src/copilot/llm.py",
                suggested_fix="Ensure the model is fully loaded.",
            )

        return StageResult("Ollama", "PASS", detail=f"Model '{model}' ready and responding")

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 7 — Database Metadata ───────────────────────────────────────────────

def run_stage7() -> StageResult:
    def check():
        # Flat imports — use the same module objects as the running app
        from src.copilot.schema_cache import load_schema_cache
        meta        = load_schema_cache()
        schemas     = meta.schemas
        tables      = meta.tables
        total_cols  = sum(len(t.columns)      for t in tables)
        total_fks   = sum(len(t.foreign_keys) for t in tables)
        if not tables:
            return StageResult(
                "Database Metadata", "WARN",
                detail="Schema loaded but no tables found.",
                suggested_fix="Verify the database has tables in the configured schema.",
            )
        return StageResult(
            "Database Metadata", "PASS",
            detail=(
                f"schemas={len(schemas)}, tables={len(tables)}, "
                f"columns={total_cols}, relationships={total_fks}"
            ),
        )

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 8 — ML Models ───────────────────────────────────────────────────────

def run_stage8() -> StageResult:
    def check():
        required_files = [
            ROOT / "models" / "best_model.pkl",
            ROOT / "models" / "feature_columns.pkl",
            ROOT / "models" / "column_medians.pkl",
        ]
        missing = [str(f.relative_to(ROOT)) for f in required_files if not f.exists()]
        if missing:
            return StageResult(
                "ML Models", "FAIL",
                detail="Missing model files:\n" + "\n".join(f"  {m}" for m in missing),
                suggested_fix="Run the training pipeline: python run_pipeline.py",
            )
        sizes  = {f.name: f"{f.stat().st_size / 1024 / 1024:.1f} MB" for f in required_files}
        detail = "  |  ".join(f"{k}: {v}" for k, v in sizes.items())
        return StageResult("ML Models", "PASS", detail=detail)

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 9 — Analytics Modules ───────────────────────────────────────────────

_ANALYTICS_MODULES = [
    "profit_analysis",
    "customer_analysis",
    "product_analysis",
    "inventory_analysis",
    "marketing_analysis",
    "returns_analysis",
    "statistical_analysis",
]


def run_stage9() -> StageResult:
    def check():
        failed = []
        for mod_name in _ANALYTICS_MODULES:
            try:
                importlib.import_module(f"analytics.{mod_name}")
            except Exception as e:
                failed.append(f"{mod_name}: {e}")

        if failed:
            return StageResult(
                "Analytics Modules", "FAIL",
                detail="Failed imports:\n" + "\n".join(f"  {f}" for f in failed),
                file_ref="src/analytics/",
                suggested_fix="Check analytics module dependencies.",
            )
        return StageResult(
            "Analytics Modules", "PASS",
            detail=f"{len(_ANALYTICS_MODULES)} modules imported successfully",
        )

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 10 — AI Agents ──────────────────────────────────────────────────────

_AGENT_MODULES = {
    "sql_agent":        "agents.sql_agent",
    "analytics_agent":  "agents.analytics_agent",
    "prediction_agent": "agents.prediction_agent",
    "report_agent":     "agents.report_agent",
}


def run_stage10() -> StageResult:
    def check():
        failed = []
        for label, module_path in _AGENT_MODULES.items():
            try:
                importlib.import_module(module_path)
            except Exception as e:
                failed.append(f"{label}: {e}")

        if failed:
            return StageResult(
                "AI Agents", "FAIL",
                detail="Failed imports:\n" + "\n".join(f"  {f}" for f in failed),
                file_ref="src/copilot/agents/",
                suggested_fix="Check agent dependencies and LLM availability.",
            )
        return StageResult(
            "AI Agents", "PASS",
            detail=f"{len(_AGENT_MODULES)} agents imported successfully",
        )

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 11 — LangGraph ──────────────────────────────────────────────────────

def run_stage11() -> StageResult:
    def check():
        # Ensure COPILOT_DIR is first — Stage 9 adds SRC_DIR which has analytics/utils.py
        # that would shadow copilot/utils.py if it comes first.
        if sys.path[0] != str(COPILOT_DIR):
            sys.path.insert(0, str(COPILOT_DIR))
        try:
            from src.copilot.graph import build_graph
            graph = build_graph()
            if graph is None:
                return StageResult(
                    "LangGraph", "FAIL",
                    detail="build_graph() returned None.",
                    file_ref="src/copilot/graph.py",
                    suggested_fix="Check graph.py for compilation errors.",
                )
            return StageResult("LangGraph", "PASS", detail="Workflow graph compiled successfully")
        except Exception as e:
            return StageResult(
                "LangGraph", "FAIL",
                detail=str(e),
                file_ref="src/copilot/graph.py",
                suggested_fix="Check graph.py and its dependencies.",
            )

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Stage 12 — Streamlit ──────────────────────────────────────────────────────

def run_stage12() -> StageResult:
    def check():
        ui_app = ROOT / "src" / "ui" / "app.py"
        if not ui_app.exists():
            return StageResult(
                "Streamlit UI", "FAIL",
                detail="src/ui/app.py not found.",
                file_ref="src/ui/app.py",
                suggested_fix="Ensure the UI file exists.",
            )
        return StageResult(
            "Streamlit UI", "PASS",
            detail=f"src/ui/app.py found ({ui_app.stat().st_size:,} bytes)",
        )

    result, elapsed = _time_stage(check)
    result.elapsed = elapsed
    return result


# ── Report Printer ────────────────────────────────────────────────────────────

STAGE_LABELS = [
    "Python",
    "Project Structure",
    "Environment",
    "Packages",
    "Database",
    "Ollama",
    "Database Metadata",
    "ML Models",
    "Analytics",
    "AI Agents",
    "LangGraph",
    "Streamlit",
]

STAGE_RUNNERS = [
    run_stage1,
    run_stage2,
    run_stage3,
    run_stage4,
    run_stage5,
    run_stage6,
    run_stage7,
    run_stage8,
    run_stage9,
    run_stage10,
    run_stage11,
    run_stage12,
]


def run_all_checks() -> list:
    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  ENTERPRISE PROFIT INTELLIGENCE PLATFORM{RESET}")
    print(f"{BOLD}  HEALTH CHECK — {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{SEP}{RESET}\n")

    results = []
    for label, runner in zip(STAGE_LABELS, STAGE_RUNNERS):
        print(f"  Running: {label}...")
        result = runner()
        result.name = label
        _print_stage(label, result)
        results.append(result)

    return results


def print_final_report(results: list) -> bool:
    hard_failed = [r for r in results if r.status == "FAIL"]
    warned      = [r for r in results if r.status == "WARN"]
    all_pass    = len(hard_failed) == 0   # WARNs do NOT block launch

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  PROJECT HEALTH REPORT{RESET}")
    print(f"{BOLD}{SEP}{RESET}")

    for label, result in zip(STAGE_LABELS, results):
        print(f"  {label:<28} {result.tag()}")

    print(f"{BOLD}{SEP}{RESET}")

    if hard_failed:
        print(f"{BOLD}{RED}  Overall  ->  SYSTEM NOT READY{RESET}")
        print()
        for r in hard_failed:
            print(f"{BOLD}{SEP}{RESET}")
            print(f"  {RED}FAILED STAGE : {r.name}{RESET}")
            if r.file_ref:
                print(f"  File         : {r.file_ref}")
            if r.detail:
                print(f"  Reason       : {r.detail}")
            if r.suggested_fix:
                print(f"  Suggested Fix: {r.suggested_fix}")
    elif warned:
        print(f"{BOLD}{YELLOW}  Overall  ->  SYSTEM READY  (with warnings){RESET}")
        print()
        for r in warned:
            print(f"{YELLOW}  WARN : {r.name} — {r.detail}{RESET}")
    else:
        print(f"{BOLD}{GREEN}  Overall  ->  SYSTEM READY{RESET}")

    print(f"{BOLD}{SEP}{RESET}\n")
    return all_pass


def main() -> bool:
    """Run all health checks. Returns True if all pass, False otherwise."""
    results = run_all_checks()
    return print_final_report(results)


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed else 1)
