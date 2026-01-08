"""Type-safe document paths and stage result models."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Type alias for document types used in path extraction
DocType = Literal["plan", "research"]

# Directory constants
RESEARCH_DIR = "thoughts/shared/research"
PLANS_DIR = "thoughts/shared/plans"

# Naming pattern: YYYY-MM-DD-description.md
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


class ResearchDocPath(BaseModel):
    """Type-safe research document path with validation."""

    doc_type: Literal["research"] = "research"
    path: str

    @field_validator("path")
    @classmethod
    def validate_research_path(cls, v: str) -> str:
        """Validate path is a research document."""
        # 1. Directory check
        if RESEARCH_DIR not in v:
            raise ValueError(f"Research document must be in {RESEARCH_DIR}/, got: {v}")

        # 2. Not a plan (explicit rejection)
        if PLANS_DIR in v:
            raise ValueError(f"Got plan document when research expected: {v}")

        # 3. Extension check
        if not v.endswith(".md"):
            raise ValueError(f"Document must be markdown (.md): {v}")

        # 4. Existence check
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Research document does not exist: {v}")

        # 5. Date prefix check
        filename = path.name
        if not DATE_PATTERN.match(filename):
            raise ValueError(f"Research doc must start with YYYY-MM-DD: {filename}")

        return str(path.resolve())  # Normalize path


class PlanDocPath(BaseModel):
    """Type-safe plan document path with validation."""

    doc_type: Literal["plan"] = "plan"
    path: str

    @field_validator("path")
    @classmethod
    def validate_plan_path(cls, v: str) -> str:
        """Validate path is a plan document."""
        # 1. Directory check
        if PLANS_DIR not in v:
            raise ValueError(f"Plan document must be in {PLANS_DIR}/, got: {v}")

        # 2. Not research (explicit rejection)
        if RESEARCH_DIR in v and PLANS_DIR not in v:
            raise ValueError(f"Got research document when plan expected: {v}")

        # 3. Extension check
        if not v.endswith(".md"):
            raise ValueError(f"Document must be markdown (.md): {v}")

        # 4. Existence check
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Plan document does not exist: {v}")

        # 5. Date prefix check (consistent with ResearchDocPath)
        filename = path.name
        if not DATE_PATTERN.match(filename):
            raise ValueError(f"Plan doc must start with YYYY-MM-DD: {filename}")

        return str(path.resolve())


class ResearchResult(BaseModel):
    """Output from research stage."""

    research_docs: list[ResearchDocPath]
    needs_implementation: bool
    summaries: list[str]
    reason: str | None = None


class DesignResult(BaseModel):
    """Output from design stage (plan + review + iterate)."""

    estimated_changes: int = Field(default=0)
    plan_doc: PlanDocPath
    summary: str


class ExecuteResult(BaseModel):
    """Output from execute stage (implement + commit)."""

    files_changed: list[str] = Field(default_factory=list)
    status: Literal["success", "partial", "failed"]
    commit_hash: str | None = None
