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

    research_summary: str = dspy.OutputField(
        desc="Summary of research findings about the codebase"
    )
    research_doc_path: str = dspy.OutputField(
        desc="Path to the detailed research document"
    )
    needs_implementation: bool = dspy.OutputField(
        desc="True if implementation needed, False if already done or unnecessary"
    )


class PlanSignature(dspy.Signature):
    """Create an implementation plan based on research findings."""

    objective: str = dspy.InputField(desc="The clarified objective to plan for")
    research_doc_path: str = dspy.InputField(desc="Path to the research document")

    plan_summary: str = dspy.OutputField(desc="Summary of the implementation plan")
    plan_doc_path: str = dspy.OutputField(desc="Path to the detailed plan document")


class DesignSignature(dspy.Signature):
    """Design stage: create, review, and iterate on an implementation plan.

    Call create_plan, review_plan, and iterate_plan tools to complete this stage.
    """

    objective: str = dspy.InputField(desc="The clarified objective to design for")
    research_doc_path: str = dspy.InputField(desc="Path to the research document")

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


class ImplementPlanSignature(dspy.Signature):
    """Implement the plan by executing all phases.

    You MUST call the implement_plan tool to execute the plan.
    """

    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    objective: str = dspy.InputField(desc="The original objective for context")

    implementation_status: str = dspy.OutputField(
        desc="Summary of implementation status: success, partial, or failed"
    )
    files_changed: str = dspy.OutputField(
        desc="List of files created, modified, or deleted during implementation"
    )


class CommitSignature(dspy.Signature):
    """Commit the changes made during implementation.

    You MUST call the commit_changes tool to create commits.
    """

    implementation_summary: str = dspy.InputField(
        desc="Summary of changes made during implementation"
    )

    commit_result: str = dspy.OutputField(desc="Commit hash(es) or status message")
