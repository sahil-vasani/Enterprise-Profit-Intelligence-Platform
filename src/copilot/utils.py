"""
utils.py — Small reusable helper functions for the AI Business Copilot.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator


def create_dir(path: Path) -> Path:
    """Create directory (and parents) if it does not exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_exists(path: Path) -> bool:
    """Check if a file exists at the given path."""
    return path.is_file()


def get_timestamp() -> str:
    """Return current timestamp as an ISO-formatted string."""
    return datetime.now().isoformat(timespec="seconds")


def save_json(data: Any, path: Path) -> None:
    """Save a Python object as a JSON file."""
    create_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def load_json(path: Path) -> Any:
    """Load a JSON file and return the parsed object."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@contextmanager
def execution_timer() -> Generator[dict[str, float], None, None]:
    """Context manager that measures elapsed time in seconds.

    Usage:
        with execution_timer() as t:
            do_work()
        print(t["elapsed"])
    """
    result: dict[str, float] = {"elapsed": 0.0}
    start = time.perf_counter()
    yield result
    result["elapsed"] = round(time.perf_counter() - start, 2)
