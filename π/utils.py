"""Utility functions for the π CLI."""

import logging


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the π CLI.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level

    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Configure root logger with basic format (keeps third-party libs at WARNING)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.WARNING,
        force=True,
    )

    # Configure our logger specifically
    logger = logging.getLogger("π")
    logger.setLevel(level)

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return logger
