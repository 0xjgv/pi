"""DSPy Workflow Module for π.

Provides PiWorkflow, a structured dspy.Module that enforces
sequential stage execution with per-stage model selection.
"""

from __future__ import annotations

import logging
from pathlib import Path

import dspy

from π.config import MAX_ITERS, Provider, get_lm
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


class IteratePlanSignature(dspy.Signature):
    """Implement the plan by making code changes."""

    objective: str = dspy.InputField(desc="The clarified objective to iterate")
    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")

    iteration_summary: str = dspy.OutputField(desc="Summary of the plan iteration")


# -----------------------------------------------------------------------------
# Workflow Module
# -----------------------------------------------------------------------------


class RPIWorkflow(dspy.Module):
    """Workflow module with per-stage ReAct agents.

    Enforces sequential execution: research → plan → review.
    Each stage uses a dedicated ReAct agent with configurable model tier.

    Attributes:
        provider: AI provider for model selection
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
        provider: Provider = Provider.Claude,
    ):
        """Initialize workflow with configuration.

        Args:
            provider: AI provider (default: Claude)
            human_input_provider: HITL provider (default: ConsoleInputProvider)
        """
        super().__init__()
        self.human_input = human_input_provider or ConsoleInputProvider()
        self.provider = provider

        # Build per-stage ReAct agents
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._review_plan_agent = self._build_review_plan_agent()

    def _build_research_agent(self) -> dspy.ReAct:
        """Build research stage agent."""
        return dspy.ReAct(
            max_iters=MAX_ITERS,
            signature=ResearchSignature,
            tools=[research_codebase],
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        """Build plan stage agent."""
        return dspy.ReAct(
            max_iters=MAX_ITERS,
            signature=PlanSignature,
            tools=[create_plan],
        )

    def _build_review_plan_agent(self) -> dspy.ReAct:
        """Build review plan stage agent."""
        return dspy.ReAct(
            max_iters=MAX_ITERS,
            signature=ReviewPlanSignature,
            tools=[review_plan],
        )

    def _validate_path(self, path_str: str | None, field_name: str) -> None:
        """Validate that output path exists on filesystem.

        Args:
            path_str: Path string from agent output
            field_name: Name of the field for error messages

        Raises:
            ValueError: If path is missing or doesn't exist
        """
        if not path_str:
            raise ValueError(f"Agent did not produce required output: {field_name}")

        path = Path(path_str)
        if not path.exists():
            raise ValueError(
                f"Output path does not exist: {path_str}\n"
                f"The agent may have fabricated this path."
            )
        logger.info("Validated %s: %s", field_name, path_str)

    def _log_trajectory(self, result: dspy.Prediction) -> None:
        """Log DSPy trajectory errors for debugging."""
        if not hasattr(result, "trajectory") or not result.trajectory:
            return
        for key, value in result.trajectory.items():
            if "observation" in key and "error" in str(value).lower():
                logger.error("DSPy trajectory error [%s]: %s", key, value)
            elif "observation" in key:
                logger.debug("DSPy trajectory [%s]: %s", key, str(value)[:200])

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute workflow: research → plan → review.

        Args:
            objective: The user's original objective/task

        Returns:
            Prediction with research_doc_path and plan_doc_path
        """
        # All stages use high tier (cached LM instance)
        lm = get_lm(self.provider, "high")

        with dspy.context(lm=lm):
            # Stage 1: Research
            researched = self._research_agent(objective=objective)
            self._log_trajectory(researched)
            self._validate_path(researched.research_doc_path, "research_doc_path")

            # Stage 2: Plan
            planned = self._plan_agent(
                objective=objective,
                research_doc_path=researched.research_doc_path,
            )
            self._log_trajectory(planned)
            self._validate_path(planned.plan_doc_path, "plan_doc_path")

            # Stage 3: Review
            reviewed = self._review_plan_agent(plan_doc_path=planned.plan_doc_path)
            self._log_trajectory(reviewed)

        return dspy.Prediction(
            research_doc_path=researched.research_doc_path,
            plan_doc_path=planned.plan_doc_path,
        )
