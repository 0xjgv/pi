"""DSPy Workflow Module for π.

Provides PiWorkflow, a structured dspy.Module that enforces
sequential stage execution with per-stage model selection.
"""

from __future__ import annotations

import logging
from pathlib import Path

import dspy

from π.config import MAX_ITERS, Provider, get_lm
from π.workflow.bridge import (
    ask_user_question,
    create_plan,
    get_extracted_path,
    iterate_plan,
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

    plan_review_feedback: str = dspy.OutputField(desc="Review and feedback on the plan")


class IteratePlanSignature(dspy.Signature):
    """Iterate on the plan based on review feedback."""

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    plan_review_feedback: str = dspy.InputField(
        desc="Review and feedback on the plan from the review stage"
    )

    iteration_summary: str = dspy.OutputField(
        desc="Summary of changes made to the plan"
    )


# -----------------------------------------------------------------------------
# Workflow Module
# -----------------------------------------------------------------------------


class RPIWorkflow(dspy.Module):
    """Workflow module with per-stage ReAct agents.

    Enforces sequential execution: research → plan → review → iterate.
    Each stage uses a dedicated ReAct agent with configurable model tier.

    Attributes:
        provider: AI provider for model selection
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

    def __init__(self):
        super().__init__()

        # Build per-stage ReAct agents
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._review_plan_agent = self._build_review_plan_agent()
        self._iterate_plan_agent = self._build_iterate_plan_agent()

    def _build_research_agent(self) -> dspy.ReAct:
        """Build research stage agent with optional human clarification."""
        return dspy.ReAct(
            signature=ResearchSignature,
            tools=[research_codebase, ask_user_question],
            max_iters=MAX_ITERS,
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        """Build plan stage agent with optional human clarification."""
        return dspy.ReAct(
            signature=PlanSignature,
            tools=[create_plan, ask_user_question],
            max_iters=MAX_ITERS,
        )

    def _build_review_plan_agent(self) -> dspy.ReAct:
        """Build review plan stage agent."""
        return dspy.ReAct(
            signature=ReviewPlanSignature,
            tools=[review_plan],
            max_iters=MAX_ITERS,
        )

    def _build_iterate_plan_agent(self) -> dspy.ReAct:
        """Build iterate plan stage agent."""
        return dspy.ReAct(
            signature=IteratePlanSignature,
            tools=[iterate_plan],
            max_iters=MAX_ITERS,
        )

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
        """Execute workflow: research → plan → review → iterate.

        Args:
            objective: The user's original objective/task

        Returns:
            Prediction with research_doc_path, plan_doc_path, and iteration_summary
        """
        # All stages use high tier (cached LM instance)
        lm = get_lm(Provider.Claude, "high")

        with dspy.context(lm=lm):
            # Stage 1: Research
            researched = self._research_agent(objective=objective)
            self._log_trajectory(researched)
            # Use validated path from context (not LLM output which may hallucinate)
            research_doc_path = get_extracted_path("research")
            if not research_doc_path:
                raise ValueError(
                    "Research stage did not produce a document at thoughts/shared/research/.\n"
                    "The agent should write the document and output 'Document saved at: <path>'."
                )

            # Stage 2: Plan
            planned = self._plan_agent(
                objective=objective,
                research_doc_path=research_doc_path,
            )
            self._log_trajectory(planned)
            # Use validated path from context (not LLM output which may hallucinate)
            plan_doc_path = get_extracted_path("plan")
            if not plan_doc_path:
                raise ValueError(
                    "Plan stage did not produce a document at thoughts/shared/plans/.\n"
                    "The agent should write the document and output 'Document saved at: <path>'."
                )

            # Stage 3: Review
            reviewed = self._review_plan_agent(plan_doc_path=plan_doc_path)
            self._log_trajectory(reviewed)

            # Stage 4: Iterate
            iterated = self._iterate_plan_agent(
                plan_review_feedback=reviewed.plan_review_feedback,
                plan_doc_path=plan_doc_path,
            )
            self._log_trajectory(iterated)

        return dspy.Prediction(
            research_doc_path=research_doc_path,
            iteration_summary=iterated.iteration_summary,
            plan_doc_path=plan_doc_path,
        )
