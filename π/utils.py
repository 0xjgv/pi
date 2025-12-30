"""Utility functions for the π CLI."""

import logging
from datetime import datetime
from functools import wraps
from os import getenv, getpid, system
from pathlib import Path
from typing import Any, Callable


def setup_logging(log_dir: Path) -> Path:
    """Configure logging for the π CLI.

    Uses delayed file creation - log file only created when first message written.

    Args:
        log_dir: Directory to store log files.

    Returns:
        Path to the log file (may not exist until first log message).
    """
    logger = logging.getLogger("π")
    logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M")
    _log_path = log_dir / f"{timestamp}.log"

    file_handler = logging.FileHandler(_log_path, delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    # Always capture DEBUG to file; logger must allow messages through
    logger.setLevel(logging.DEBUG)

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return _log_path


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
