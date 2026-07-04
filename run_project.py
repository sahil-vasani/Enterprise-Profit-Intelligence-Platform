"""
run_project.py — Production launcher for the Enterprise Profit Intelligence Platform.
Runs health_check.py first. On success, launches Streamlit. On failure, exits cleanly.
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
SEP    = "=" * 60


def _print_banner():
    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Enterprise Profit Intelligence Platform{RESET}")
    print(f"{BOLD}  Production Launcher{RESET}")
    print(f"{BOLD}{SEP}{RESET}\n")


def run_health_check() -> bool:
    """
    Execute health_check.py as a subprocess.
    Returns True if all checks pass (exit code 0), False otherwise.
    """
    health_script = ROOT / "health_check.py"
    if not health_script.exists():
        print(f"{RED}  ERROR: health_check.py not found at {health_script}{RESET}")
        return False

    result = subprocess.run(
        [sys.executable, str(health_script)],
        cwd=str(ROOT),
    )
    return result.returncode == 0


def launch_streamlit():
    """Launch Streamlit and block until the user stops it."""
    ui_app = ROOT / "src" / "ui" / "app.py"
    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}{GREEN}  SYSTEM READY — Launching Streamlit...{RESET}")
    print(f"{BOLD}{SEP}{RESET}\n")

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(ui_app)],
        cwd=str(ROOT),
    )


def main():
    _print_banner()

    print(f"{BOLD}  Step 1: Running health checks...{RESET}\n")
    passed = run_health_check()

    if passed:
        launch_streamlit()
    else:
        print(f"\n{BOLD}{SEP}{RESET}")
        print(f"{BOLD}{RED}  PROJECT CANNOT START{RESET}")
        print(f"{BOLD}{SEP}{RESET}")
        print(f"  One or more health checks failed.")
        print(f"  Review the report above, fix the issues, then re-run:")
        print(f"\n    {YELLOW}python run_project.py{RESET}\n")
        print(f"  Or run the health check standalone:")
        print(f"\n    {YELLOW}python health_check.py{RESET}\n")
        print(f"{BOLD}{SEP}{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
