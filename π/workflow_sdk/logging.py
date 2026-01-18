"""Logging utilities for queue-based workflow."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from π.console import console

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


@dataclass
class QueueMetrics:
    """Metrics for a queue operation."""

    stage: str
    operation: str
    duration_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0


def log_queue_send(stage: str, message: str) -> None:
    """Log message sent to queue."""
    # Truncate long messages for logging
    msg_preview = message[:100] + "..." if len(message) > 100 else message
    logger.info("[%s] -> %s", stage, msg_preview)
    console.print(f"[dim]-> {stage}[/dim]", style="blue")


def log_queue_receive(stage: str, output: Any, duration_ms: float) -> None:
    """Log response received from queue."""
    output_preview = str(output)[:100]
    logger.info("[%s] <- %s... (%.0fms)", stage, output_preview, duration_ms)
    console.print(f"[dim]<- {stage} ({duration_ms:.0f}ms)[/dim]", style="green")


@contextmanager
def timed_queue_operation(stage: str, operation: str) -> Generator[None]:
    """Context manager for timing queue operations."""
    start = time.perf_counter()
    logger.debug("[%s] %s starting", stage, operation)
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug("[%s] %s completed in %.0fms", stage, operation, duration_ms)
