"""Centralized configuration constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowConfig:
    """Workflow execution settings."""

    max_iters: int = 5
    base_retry_delay: float = 1.0
    max_retries: int = 3


@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout settings in seconds."""

    user_input: float = 300.0
    hook_command: int = 30
    git_command: int = 5


@dataclass(frozen=True)
class RetentionConfig:
    """Retention periods."""

    logs_days: int = 7
    documents_days: int = 5
    checkpoint_hours: int = 24
    memory_store_days: int = 30


@dataclass(frozen=True)
class DocSyncConfig:
    """Documentation sync thresholds."""

    files_threshold: int = 10


# Singleton configs
WORKFLOW = WorkflowConfig()
TIMEOUTS = TimeoutConfig()
RETENTION = RetentionConfig()
DOC_SYNC = DocSyncConfig()
