"""Pydantic models for Claude SDK structured outputs."""

from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Research Stage
# =============================================================================


class ResearchOutput(BaseModel):
    """Output from research_codebase tool call."""

    research_docs: list[str] = Field(description="Paths to created research documents")
    summaries: list[str] = Field(description="Key findings from research")
    needs_implementation: bool = Field(
        description="True if code changes needed, False if objective already satisfied"
    )
    reason: str | None = Field(
        default=None, description="Explanation if no implementation needed"
    )


# =============================================================================
# Design Stage Sub-outputs
# =============================================================================


class CreatePlanOutput(BaseModel):
    """Output from create_plan tool call."""

    plan_path: str = Field(description="Path to created plan document")
    summary: str = Field(description="Brief summary of the plan")


class ReviewPlanOutput(BaseModel):
    """Output from review_plan tool call."""

    approved: bool = Field(description="True if plan passes review")
    issues: list[str] = Field(
        default_factory=list,
        description="Issues found during review (empty if approved)",
    )
    severity: Literal["none", "minor", "major"] = Field(
        default="none", description="Severity of issues found"
    )


class IteratePlanOutput(BaseModel):
    """Output from iterate_plan tool call."""

    plan_path: str = Field(description="Path to updated plan document")
    changes_made: list[str] = Field(
        description="List of changes made to address issues"
    )
    summary: str = Field(description="Summary of iteration")


class DesignOutput(BaseModel):
    """Final aggregated output from design stage."""

    plan_path: str = Field(description="Path to final plan document")
    summary: str = Field(description="Summary of the plan")
    iterations: int = Field(default=0, description="Number of review-iterate cycles")
    estimated_changes: int = Field(
        default=0, description="Estimated number of file changes"
    )


# =============================================================================
# Execute Stage Sub-outputs
# =============================================================================


class ImplementOutput(BaseModel):
    """Output from implement_plan tool call."""

    files_changed: list[str] = Field(default_factory=list, description="Files modified")
    status: Literal["success", "partial", "failed"] = Field(
        description="Implementation status"
    )
    issues: list[str] = Field(
        default_factory=list, description="Issues encountered during implementation"
    )


class CommitOutput(BaseModel):
    """Output from commit_changes tool call."""

    commit_hash: str | None = Field(
        default=None,
        description="Git commit hash, None if no changes or commit failed",
    )
    message: str = Field(description="Commit message used")


class ExecuteOutput(BaseModel):
    """Final aggregated output from execute stage."""

    files_changed: list[str] = Field(default_factory=list)
    status: Literal["success", "partial", "failed"]
    commit_hash: str | None = None


# =============================================================================
# Orchestrator Messages
# =============================================================================


class OrchestratorDecision(BaseModel):
    """Orchestrator's decision after receiving stage response."""

    action: Literal["continue", "iterate", "proceed", "abort"] = Field(
        description="Next action to take"
    )
    target_stage: Literal["research", "design", "execute"] | None = Field(
        default=None, description="Stage to send next message to"
    )
    message: str | None = Field(
        default=None, description="Message to send to target stage"
    )
    reason: str = Field(description="Reasoning for this decision")
