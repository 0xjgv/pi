"""Centralized configuration constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionConfig:
    """Retention periods."""

    checkpoint_hours: int = 24
    documents_days: int = 5
    logs_days: int = 7


RETENTION = RetentionConfig()
