"""DSPy Workflow Module for π.

Provides PiWorkflow, a structured dspy.Module that enforces
sequential stage execution with per-stage model selection.
"""

from __future__ import annotations

import logging
from pathlib import Path

import dspy

from π.config import DEFAULT_STAGE_CONFIGS, Provider, Stage, StageConfig, get_lm
from π.support import ConsoleInputProvider, HumanInputProvider
from π.workflow.bridge import (
    create_plan,
    research_codebase,
    review_plan,
)

logger = logging.getLogger(__name__)

# Default path for optimized workflow
DEFAULT_OPTIMIZED_PATH = Path("π/optimized_workflow.json")

# -----------------------------------------------------------------------------
# Stage Signatures
# -----------------------------------------------------------------------------


class ClarifySignature(dspy.Signature):
    """Clarify the user's objective through interactive questioning."""

    objective: str = dspy.InputField(desc="The user's original objective or task")
    clarified_objective: str = dspy.OutputField(
        desc="The refined, unambiguous objective after clarification"
    )


class ResearchSignature(dspy.Signature):
    """Research the codebase to understand patterns and architecture."""

    objective: str = dspy.InputField(desc="The clarified objective to research")
    research_summary: str = dspy.OutputField(
        desc="Summary of research findings about the codebase"
    )
    research_doc_path: str = dspy.OutputField(
        desc="Path to the detailed research document"
    )


class PlanSignature(dspy.Signature):
    """Create an implementation plan based on research findings."""

    objective: str = dspy.InputField(desc="The clarified objective to plan for")
    research_doc_path: str = dspy.InputField(desc="Path to the research document")
    plan_summary: str = dspy.OutputField(desc="Summary of the implementation plan")
    plan_doc_path: str = dspy.OutputField(desc="Path to the detailed plan document")


class ReviewPlanSignature(dspy.Signature):
    """Review the plan to ensure it is complete and accurate."""

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    review_summary: str = dspy.OutputField(desc="Summary of the plan review")


class ImplementSignature(dspy.Signature):
    """Implement the plan by making code changes."""

    objective: str = dspy.InputField(desc="The clarified objective to implement")
    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    implementation_summary: str = dspy.OutputField(
        desc="Summary of the implementation changes made"
    )


# -----------------------------------------------------------------------------
# Workflow Module
# -----------------------------------------------------------------------------


class RPIWorkflow(dspy.Module):
    """Workflow module with per-stage ReAct agents.

    Enforces sequential execution: clarify → research → plan → review → implement.
    Each stage uses a dedicated ReAct agent with configurable model tier.

    Attributes:
        provider: AI provider for model selection
        configs: Per-stage configuration (model tier, max iterations)
        human_input: Provider for human-in-the-loop interactions
    """

    @classmethod
    def load_optimized(
        cls,
        path: str | Path = DEFAULT_OPTIMIZED_PATH,
        **kwargs,
    ) -> "RPIWorkflow":
        """Load GEPA-optimized workflow if available.

        Falls back to unoptimized workflow if no saved state exists.

        Args:
            path: Path to optimized workflow JSON
            **kwargs: Additional arguments passed to __init__ if fallback

        Returns:
            RPIWorkflow instance (optimized if available, default otherwise)
        """
        path = Path(path)
        if path.exists():
            logger.info("Loading optimized workflow from %s", path)
            # dspy.Module.load() loads from JSON
            return cls.load(path=str(path))  # type: ignore[call-arg]
        logger.info("No optimized workflow found, using default")
        return cls(**kwargs)

    def __init__(
        self,
        *,
        human_input_provider: HumanInputProvider | None = None,
        stage_configs: dict[Stage, StageConfig] | None = None,
        provider: Provider = Provider.Claude,
    ):
        """Initialize workflow with configuration.

        Args:
            provider: AI provider (default: Claude)
            stage_configs: Custom per-stage configs (merged with defaults)
            human_input_provider: HITL provider (default: ConsoleInputProvider)
        """
        super().__init__()
        self.configs = {**DEFAULT_STAGE_CONFIGS, **(stage_configs or {})}
        self.human_input = human_input_provider or ConsoleInputProvider()
        self.provider = provider

        # Build per-stage ReAct agents
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._review_plan_agent = self._build_review_plan_agent()
        # self._iterate_plan_agent = self._build_iterate_plan_agent()

    def _build_research_agent(self) -> dspy.ReAct:
        """Build research stage agent."""
        return dspy.ReAct(
            max_iters=self.configs[Stage.RESEARCH].max_iters,
            signature=ResearchSignature,
            tools=[research_codebase],
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        """Build plan stage agent."""
        return dspy.ReAct(
            max_iters=self.configs[Stage.PLAN].max_iters,
            signature=PlanSignature,
            tools=[create_plan],
        )

    def _build_review_plan_agent(self) -> dspy.ReAct:
        """Build review plan stage agent."""
        return dspy.ReAct(
            max_iters=self.configs[Stage.REVIEW_PLAN].max_iters,
            signature=ReviewPlanSignature,
            tools=[review_plan],
        )

    # def _build_iterate_plan_agent(self) -> dspy.ReAct:
    #     """Build iterate plan stage agent."""
    #     return dspy.ReAct(
    #         max_iters=self.configs[Stage.ITERATE_PLAN].max_iters,
    #         signature=IteratePlanSignature,
    #         tools=[iterate_plan],
    #     )

    def _run_stage(
        self, *, stage: Stage, agent: dspy.ReAct, **kwargs
    ) -> dspy.Prediction:
        """Run agent with stage-specific model via dspy.context().

        Args:
            stage: The workflow stage being executed
            agent: The ReAct agent for this stage
            **kwargs: Arguments to pass to the agent

        Returns:
            Agent's prediction output
        """
        lm = get_lm(self.provider, self.configs[stage].model_tier)
        with dspy.context(lm=lm):
            result = agent(**kwargs)

        # Log DSPy trajectory to expose any tool execution errors
        # TODO: raise an error and let it be handled by the caller (including logging)
        if hasattr(result, "trajectory") and result.trajectory:
            for key, value in result.trajectory.items():
                if "observation" in key and "error" in str(value).lower():
                    logger.error("DSPy trajectory error [%s]: %s", key, value)
                elif "observation" in key:
                    logger.debug("DSPy trajectory [%s]: %s", key, str(value)[:200])

        return result

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute workflow with enforced stage order.

        Stages execute sequentially: research → plan → review -> iterate_plan.
        Each stage's output feeds into the next stage.

        Args:
            objective: The user's original objective/task

        Returns:
            Prediction containing all stage outputs:
            - research_doc_path: Path to research document
            - plan_doc_path: Path to plan document
        """
        # Stage 1: Research (deep codebase exploration)
        researched = self._run_stage(
            agent=self._research_agent,
            stage=Stage.RESEARCH,
            objective=objective,
        )

        # Stage 2: Plan (architectural reasoning)
        planned = self._run_stage(
            research_doc_path=researched.research_doc_path,
            agent=self._plan_agent,
            objective=objective,
            stage=Stage.PLAN,
        )

        # Stage 3: Review Plan (validation)
        self._run_stage(
            plan_doc_path=planned.plan_doc_path,
            agent=self._review_plan_agent,
            stage=Stage.REVIEW_PLAN,
        )

        # Stage 4: Iterate Plan (code generation)
        # implemented = self._run_stage(
        #     plan_doc_path=planned.plan_doc_path,
        #     agent=self._iterate_plan_agent,
        #     stage=Stage.ITERATE_PLAN,
        # )

        return dspy.Prediction(
            research_doc_path=researched.research_doc_path,
            plan_doc_path=planned.plan_doc_path,
        )
