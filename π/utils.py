"""Utility functions for the π CLI."""

import logging
import subprocess
from collections.abc import Callable
from functools import wraps
from os import getenv, getpid, system
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_MARKERS = {
    ".git",
    "CLAUDE.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
}


def get_project_root(start_path: Path | None = None) -> Path:
    """Detect project root: CWD if has markers, else git root, else CWD.

    Args:
        start_path: Starting path for detection. Defaults to CWD.

    Returns:
        Detected project root path.
    """
    cwd = start_path or Path.cwd()

    # Check if CWD has project markers
    if any((cwd / m).exists() for m in PROJECT_MARKERS):
        return cwd

    # Fallback: git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Final fallback: CWD
    return cwd


def prevent_sleep(func: Callable[..., Any]) -> Callable[..., Any]:
    """Prevents the system from sleeping while the function is running"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        pid = getpid()
        system(f"caffeinate -disuw {pid}&")
        return func(*args, **kwargs)

    return wrapper


def speak(text: str) -> None:
    """Speaks the given text using the system's default speech synthesizer."""
    if getenv("PYTEST_CURRENT_TEST"):
        return
    system(f"say '{text}'")
