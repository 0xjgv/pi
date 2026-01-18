"""Structured output models for workflow orchestrator.

These Pydantic models define the contract for workflow output. The structured
output schema acts as a forcing function - the orchestrator MUST call tools
to satisfy required fields (can't hallucinate file paths, commit hashes, etc.).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkflowOutput(BaseModel):
    """Single orchestrator output - tools provide ground truth for all fields.

    The schema uses optional fields for conditional workflow paths:
    - needs_implementation=False → plan/review/execute fields remain None
    - review_approved=False → triggers iterate_plan loop
    - files_changed=[] → commit_hash remains None
    """

    # === Research Phase (always required) ===
    research_doc_path: str = Field(
        description="Path to research document from research_codebase tool"
    )
    research_summary: str = Field(description="Summary of findings from research")
    needs_implementation: bool = Field(
        description="Whether implementation is needed based on research"
    )

    # === Plan Phase (optional - only if needs_implementation=True) ===
    plan_doc_path: str | None = Field(
        default=None,
        description="Path to plan document from create_plan tool",
    )

    # === Review Phase (optional - only if plan was created) ===
    review_approved: bool | None = Field(
        default=None,
        description="Whether plan was approved by review_plan tool",
    )
    review_iteration_count: int = Field(
        default=0,
        description="Number of iterate_plan cycles before approval",
    )

    # === Execute Phase (optional - only if review approved) ===
    files_changed: list[str] = Field(
        default_factory=list,
        description="Files modified by implement_plan tool",
    )

    # === Commit Phase (optional - only if files changed) ===
    commit_hash: str | None = Field(
        default=None,
        description="Git commit hash from commit_changes tool",
    )

    # === Final Status ===
    status: Literal["complete", "no_changes_needed", "failed"] = Field(
        description="Final workflow status"
    )
    summary: str = Field(description="Human-readable summary of what was accomplished")
