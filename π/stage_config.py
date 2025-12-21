"""Stage configuration for π workflow module."""

from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    """Workflow stages."""

    CLARIFY = "clarify"
    RESEARCH = "research"
    PLAN = "plan"
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
    Stage.CLARIFY: StageConfig(
        model_tier="low",
        max_iters=5,
        description="Fast model for human interaction loops",
    ),
    Stage.RESEARCH: StageConfig(
        model_tier="high",
        max_iters=3,
        description="Powerful model for deep codebase exploration",
    ),
    Stage.PLAN: StageConfig(
        model_tier="high",
        max_iters=3,
        description="Powerful model for architectural reasoning",
    ),
    Stage.IMPLEMENT: StageConfig(
        model_tier="med",
        max_iters=5,
        description="Balanced model for code generation",
    ),
}
