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
    create_commit,
    create_plan,
    get_extracted_path,
    implement_plan,
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
    """Iterate on the plan based on review feedback.

    You MUST call the iterate_plan tool to make changes to the plan document.
    """

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    plan_review_feedback: str = dspy.InputField(
        desc="Review feedback to incorporate via iterate_plan tool"
    )

    changes_made: str = dspy.OutputField(
        desc="Detailed list of changes made to the plan via iterate_plan tool. "
        "Must describe actual modifications (not 'no changes needed')."
    )
    iteration_summary: str = dspy.OutputField(desc="Summary of the iteration process")


class ImplementSignature(dspy.Signature):
    """Execute the implementation plan, writing code changes.

    You MUST call the implement_plan tool to execute the plan.
    """

    plan_doc_path: str = dspy.InputField(desc="Path to the approved plan document")

    files_changed: str = dspy.OutputField(
        desc="List of files created/modified during implementation"
    )
    implementation_summary: str = dspy.OutputField(
        desc="Summary of what was implemented"
    )


class CommitSignature(dspy.Signature):
    """Create a git commit for the implementation changes.

    You MUST call the create_commit tool to commit changes.
    """

    files_changed: str = dspy.InputField(desc="Files modified during implementation")
    implementation_summary: str = dspy.InputField(desc="Summary of implementation")

    commit_hash: str = dspy.OutputField(desc="Git commit SHA")
    commit_message: str = dspy.OutputField(desc="The commit message used")


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

    def __init__(self, *, include_implement: bool = False):
        """Initialize workflow with per-stage ReAct agents.

        Args:
            include_implement: If True, include implement and commit stages (5 & 6).
                Defaults to False for backward compatibility.
        """
        super().__init__()
        self._include_implement = include_implement

        # Build per-stage ReAct agents
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._review_plan_agent = self._build_review_plan_agent()
        self._iterate_plan_agent = self._build_iterate_plan_agent()

        # Optional stages 5 & 6
        if include_implement:
            self._implement_agent = self._build_implement_agent()
            self._commit_agent = self._build_commit_agent()

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

    def _build_implement_agent(self) -> dspy.ReAct:
        """Build implement stage agent."""
        return dspy.ReAct(
            signature=ImplementSignature,
            tools=[implement_plan],
            max_iters=MAX_ITERS,
        )

    def _build_commit_agent(self) -> dspy.ReAct:
        """Build commit stage agent."""
        return dspy.ReAct(
            signature=CommitSignature,
            tools=[create_commit],
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

    def _validate_tool_usage(
        self,
        result: dspy.Prediction,
        required_tool: str,
        stage_name: str,
    ) -> None:
        """Validate that a required tool was called in the trajectory.

        Args:
            result: DSPy prediction with trajectory
            required_tool: Tool name that must have been called
            stage_name: Name of the stage for error messages

        Raises:
            ValueError: If the required tool was not called
        """
        if not hasattr(result, "trajectory") or not result.trajectory:
            logger.warning(
                "%s: No trajectory found, cannot validate tool usage", stage_name
            )
            return

        tool_names = [
            v
            for k, v in result.trajectory.items()
            if k.startswith("tool_name_") and v != "finish"
        ]

        if required_tool not in tool_names:
            logger.error(
                "%s: Required tool '%s' was NOT called. Tools used: %s",
                stage_name,
                required_tool,
                tool_names,
            )
            raise ValueError(
                f"{stage_name} failed: {required_tool} tool was not invoked. "
                f"Agent shortcut by directly producing output. Tools called: {tool_names}"
            )

        logger.debug(
            "%s: Tool usage validated - %s was called", stage_name, required_tool
        )

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute workflow: research -> plan -> review -> iterate [-> implement -> commit].

        Args:
            objective: The user's original objective/task

        Returns:
            Prediction with research_doc_path, plan_doc_path, changes_made, iteration_summary,
            and optionally files_changed, implementation_summary, commit_hash, commit_message.
        """
        # All stages use high tier (cached LM instance)
        lm = get_lm(Provider.Claude, "high")
        total_stages = 6 if self._include_implement else 4

        with dspy.context(lm=lm):
            # Stage 1: Research
            logger.info("=== STAGE 1/%d: RESEARCH ===", total_stages)
            logger.debug("Research input: objective=%s", objective[:200])
            researched = self._research_agent(objective=objective)
            self._log_trajectory(researched)
            # Use validated path from context (not LLM output which may hallucinate)
            research_doc_path = get_extracted_path("research")
            if not research_doc_path:
                raise ValueError(
                    "Research stage did not produce a document at thoughts/shared/research/.\n"
                    "The agent should write the document and output 'Document saved at: <path>'."
                )
            logger.info("Research complete: %s", research_doc_path)

            # Stage 2: Plan
            logger.info("=== STAGE 2/%d: PLAN ===", total_stages)
            logger.debug(
                "Plan input: objective=%s, research_doc=%s",
                objective[:100],
                research_doc_path,
            )
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
            logger.info("Plan complete: %s", plan_doc_path)

            # Stage 3: Review
            logger.info("=== STAGE 3/%d: REVIEW ===", total_stages)
            logger.debug("Review input: plan_doc=%s", plan_doc_path)
            reviewed = self._review_plan_agent(plan_doc_path=plan_doc_path)
            self._log_trajectory(reviewed)
            logger.info(
                "Review complete: feedback=%s", reviewed.plan_review_feedback[:100]
            )

            # Stage 4: Iterate
            logger.info("=== STAGE 4/%d: ITERATE ===", total_stages)
            logger.debug(
                "Iterate input: plan_doc=%s, feedback=%s",
                plan_doc_path,
                reviewed.plan_review_feedback[:200],
            )
            iterated = self._iterate_plan_agent(
                plan_review_feedback=reviewed.plan_review_feedback,
                plan_doc_path=plan_doc_path,
            )
            self._log_trajectory(iterated)
            self._validate_tool_usage(iterated, "iterate_plan", "Iterate stage")
            logger.info(
                "Iterate complete: changes_made=%s", iterated.changes_made[:100]
            )

            # Optional stages 5 & 6: Implement and Commit
            if self._include_implement:
                # Stage 5: Implement
                logger.info("=== STAGE 5/%d: IMPLEMENT ===", total_stages)
                logger.debug("Implement input: plan_doc=%s", plan_doc_path)
                implemented = self._implement_agent(plan_doc_path=plan_doc_path)
                self._log_trajectory(implemented)
                self._validate_tool_usage(
                    implemented, "implement_plan", "Implement stage"
                )
                logger.info(
                    "Implement complete: files_changed=%s",
                    implemented.files_changed[:100],
                )

                # Stage 6: Commit
                logger.info("=== STAGE 6/%d: COMMIT ===", total_stages)
                logger.debug(
                    "Commit input: files=%s, summary=%s",
                    implemented.files_changed[:100],
                    implemented.implementation_summary[:100],
                )
                committed = self._commit_agent(
                    files_changed=implemented.files_changed,
                    implementation_summary=implemented.implementation_summary,
                )
                self._log_trajectory(committed)
                self._validate_tool_usage(committed, "create_commit", "Commit stage")
                logger.info(
                    "Commit complete: hash=%s, message=%s",
                    committed.commit_hash,
                    committed.commit_message[:50],
                )

                return dspy.Prediction(
                    research_doc_path=research_doc_path,
                    plan_doc_path=plan_doc_path,
                    changes_made=iterated.changes_made,
                    iteration_summary=iterated.iteration_summary,
                    files_changed=implemented.files_changed,
                    implementation_summary=implemented.implementation_summary,
                    commit_hash=committed.commit_hash,
                    commit_message=committed.commit_message,
                )

        return dspy.Prediction(
            research_doc_path=research_doc_path,
            plan_doc_path=plan_doc_path,
            changes_made=iterated.changes_made,
            iteration_summary=iterated.iteration_summary,
        )
