"""LLM model configuration and factory functions."""

import logging
from functools import lru_cache

from π.bridge.lm import ClaudeCodeLM
from π.core.enums import Tier, WorkflowStage

logger = logging.getLogger(__name__)

# Tier → Model mapping (Claude only)
TIER_TO_MODEL: dict[Tier, str] = {
    Tier.LOW: "claude-haiku-4-5-20251001",
    Tier.MED: "claude-sonnet-4-5-20250929",
    Tier.HIGH: "claude-opus-4-5-20251101",
}

# WorkflowStage → Model tier mapping
STAGE_TIERS: dict[WorkflowStage, Tier] = {
    WorkflowStage.RESEARCH: Tier.HIGH,
    WorkflowStage.DESIGN: Tier.HIGH,
    WorkflowStage.EXECUTE: Tier.HIGH,
}

# Maximum ReAct iterations (same for all stages)
MAX_ITERS = 5


@lru_cache(maxsize=3)
def get_lm(tier: Tier) -> ClaudeCodeLM:
    """Get cached ClaudeCodeLM instance for tier.

    Args:
        tier: Model tier (low, med, high)

    Returns:
        Configured ClaudeCodeLM instance
    """
    model = TIER_TO_MODEL.get(tier, "claude-sonnet-4-5-20250929")
    logger.debug("Creating ClaudeCodeLM: tier=%s → model=%s", tier, model)
    return ClaudeCodeLM(model=model)
