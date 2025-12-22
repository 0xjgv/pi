"""DSPy router for classifying objectives into execution modes."""

from enum import StrEnum
from logging import Logger
from typing import Literal

import dspy

from π.config import Provider, get_lm


class ExecutionMode(StrEnum):
    """Execution modes for objective handling."""

    SIMPLE = "simple"
    WORKFLOW = "workflow"


class ObjectiveRouter(dspy.Signature):
    """Classify objective to determine execution mode.

    'simple': Questions, lookups, single-file changes, 1-3 tool calls
    'workflow': Multi-file implementations, features needing research/planning
    """

    objective: str = dspy.InputField()
    reasoning: str = dspy.OutputField(desc="Brief complexity analysis")
    mode: Literal["simple", "workflow"] = dspy.OutputField()


def classify_objective(
    objective: str,
    *,
    provider: Provider,
    logger: Logger,
) -> ExecutionMode:
    """Classify objective using ChainOfThought reasoning.

    Router always uses low-tier model for fast classification.

    Args:
        objective: The user's objective/task
        provider: AI provider for model selection
        logger: Logger instance

    Returns:
        ExecutionMode.SIMPLE or ExecutionMode.WORKFLOW
    """
    lm = get_lm(provider=provider, tier="low")
    router = dspy.ChainOfThought(ObjectiveRouter)

    with dspy.context(lm=lm):
        result = router(objective=objective)

    logger.debug("Router: %s (reason: %s)", result.mode, result.reasoning[:100])
    return ExecutionMode(result.mode)
