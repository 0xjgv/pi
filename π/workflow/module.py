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

    Call create_plan and review_plan tools to complete this stage.
    """

    objective: str = dspy.InputField(desc="The clarified objective to design for")
    research_doc_paths: list[str] = dspy.InputField(
        desc="Paths to the research documents"
    )
    research_summaries: list[str] = dspy.InputField(
        desc="Summaries of the research findings"
    )

    plan_doc_path: str = dspy.OutputField(desc="Path to the final plan document")
    plan_summary: str = dspy.OutputField(desc="Summary of the design and iterations")


class ExecuteSignature(dspy.Signature):
    """Execute stage: implement the plan and commit changes.

    Call implement_plan and commit_changes tools to complete this stage.
    """

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    objective: str = dspy.InputField(desc="The original objective for context")

    status: str = dspy.OutputField(desc="Status: success, partial, or failed")
    files_changed: str = dspy.OutputField(desc="Comma-separated list of files changed")
    commit_hash: str = dspy.OutputField(desc="Git commit hash or 'none' if no commit")
