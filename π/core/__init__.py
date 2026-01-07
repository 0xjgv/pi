"""Core configuration and enums for π workflow.

This module is a leaf layer with no imports from other π modules,
breaking potential circular dependencies.
"""

from π.core.enums import Provider, Stage, Tier
from π.core.errors import AgentExecutionError
from π.core.models import (
    DEFAULT_MODELS,
    MAX_ITERS,
    PROVIDER_MODELS,
    STAGE_TIERS,
    get_lm,
)

__all__ = [
    "DEFAULT_MODELS",
    "MAX_ITERS",
    "PROVIDER_MODELS",
    "STAGE_TIERS",
    "AgentExecutionError",
    "Provider",
    "Stage",
    "Tier",
    "get_lm",
]
