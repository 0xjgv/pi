"""Utility functions for the π CLI."""

import logging
from datetime import datetime
from pathlib import Path

_log_path: Path | None = None


def get_log_path() -> Path | None:
    """Return the current session's log path (if verbose mode)."""
    return _log_path


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the π CLI.

    Args:
        verbose: If True, route DEBUG logs to file; console stays clean

    Returns:
        Configured logger instance
    """
    global _log_path

    logger = logging.getLogger("π")
    logger.handlers.clear()

    if verbose:
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
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)
        _log_path = None

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return logger
