"""Core configuration and enums for π workflow.

This module is a leaf layer with no imports from other π modules,
breaking potential circular dependencies.
"""

from π.core.enums import Provider, Tier, WorkflowStage
from π.core.errors import AgentExecutionError
from π.core.models import (
    MAX_ITERS,
    PROVIDER_MODELS,
    STAGE_TIERS,
    get_lm,
)

__all__ = [
    "MAX_ITERS",
    "PROVIDER_MODELS",
    "STAGE_TIERS",
    "AgentExecutionError",
    "Provider",
    "Tier",
    "WorkflowStage",
    "get_lm",
]
