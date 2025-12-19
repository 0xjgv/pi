"""Utility functions for the π CLI."""

import logging
from datetime import datetime
from pathlib import Path


def setup_logging() -> Path:
    """Configure logging for the π CLI.

    Returns:
        Path to the log file
    """
    logger = logging.getLogger("π")
    logger.handlers.clear()

    # Always create log files
    log_dir = Path.home() / ".π" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    _log_path = log_dir / f"{timestamp}.log"

    file_handler = logging.FileHandler(_log_path)
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
