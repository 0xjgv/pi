"""DSPy Workflow Module for π.

Provides stage signatures for workflow modules.
"""

from __future__ import annotations

import dspy

# -----------------------------------------------------------------------------
# Stage Signatures
# -----------------------------------------------------------------------------


class ResearchSignature(dspy.Signature):
    """Research the codebase to understand patterns and architecture."""

    objective: str = dspy.InputField(desc="The clarified objective to research")

    stage: str = dspy.OutputField(desc="Always 'research'")
    research_summaries: list[str] = dspy.OutputField(
        desc="Summaries of research findings about the codebase"
    )
    research_doc_paths: list[str] = dspy.OutputField(
        desc="Paths to the research documents"
    )
    needs_implementation: bool = dspy.OutputField(
        desc="True if implementation needed, False if already done or unnecessary"
    )
    task_status: str = dspy.OutputField(
        desc="'complete' when finished, 'needs_clarification' if user input needed"
    )


class DesignSignature(dspy.Signature):
    """Design stage: create and review an implementation plan.

    Workflow:
    1. Call create_plan ONCE to produce initial plan
    2. Call review_plan to get feedback
    3. If review has issues, call iterate_plan with the review feedback
    4. Repeat review -> iterate until approved

    Never call create_plan twice. Use iterate_plan to address review feedback.
    """

    objective: str = dspy.InputField(desc="The clarified objective to design for")
    research_doc_paths: list[str] = dspy.InputField(
        desc="Paths to the research documents"
    )
    research_summaries: list[str] = dspy.InputField(
        desc="Summaries of the research findings"
    )

    stage: str = dspy.OutputField(desc="Always 'design'")
    plan_doc_path: str = dspy.OutputField(desc="Path to the final plan document")
    plan_summary: str = dspy.OutputField(desc="Summary of the design and iterations")
    iterations: int = dspy.OutputField(
        desc="Number of review->iterate cycles (0 if review passed immediately)"
    )


class ExecuteSignature(dspy.Signature):
    """Execute stage: implement the plan and commit changes.

    Call implement_plan and commit_changes tools to complete this stage.
    """

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    objective: str = dspy.InputField(desc="The original objective for context")

    stage: str = dspy.OutputField(desc="Always 'execute'")
    status: str = dspy.OutputField(desc="Status: success, partial, or failed")
    files_changed: str = dspy.OutputField(desc="Comma-separated list of files changed")
    commit_hash: str = dspy.OutputField(desc="Git commit hash or 'none' if no commit")
