"""Stage configuration for π workflow module."""

from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    """Workflow stages."""

    CLARIFY = "clarify"
    RESEARCH = "research"
    PLAN = "plan"
    REVIEW_PLAN = "review_plan"
    IMPLEMENT = "implement"


@dataclass(frozen=True)
class StageConfig:
    """Immutable configuration for a workflow stage.

    Attributes:
        model_tier: The model tier to use ("low", "med", "high")
        max_iters: Maximum ReAct iterations for this stage
        description: Human-readable description of the stage purpose
    """

    model_tier: str
    max_iters: int
    description: str = ""


DEFAULT_STAGE_CONFIGS: dict[Stage, StageConfig] = {
    Stage.RESEARCH: StageConfig(
        description="Powerful model for deep codebase exploration",
        model_tier="high",
        max_iters=3,
    ),
    Stage.PLAN: StageConfig(
        description="Powerful model for architectural reasoning",
        model_tier="high",
        max_iters=3,
    ),
    Stage.REVIEW_PLAN: StageConfig(
        description="Review plan for completeness and accuracy",
        model_tier="high",
        max_iters=3,
    ),
    # TODO: implement the iterate_plan
    # Stage.ITERATE_PLAN: StageConfig(
    #     description="Iterate plan for completeness and accuracy",
    #     model_tier="high",
    #     max_iters=3,
    # ),
}
