"""Core configuration and enums for π workflow.

This module is a leaf layer with no imports from other π modules,
breaking potential circular dependencies.
"""

from π.core.enums import Tier, WorkflowStage
from π.core.errors import AgentExecutionError
from π.core.models import (
    MAX_ITERS,
    STAGE_TIERS,
    TIER_TO_MODEL,
    get_lm,
)

__all__ = [
    "MAX_ITERS",
    "STAGE_TIERS",
    "TIER_TO_MODEL",
    "AgentExecutionError",
    "Tier",
    "WorkflowStage",
    "get_lm",
]
