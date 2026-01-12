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


def _validate_doc_path(
    v: str,
    *,
    required_dir: str,
    rejected_dir: str | None,
    doc_type: str,
) -> str:
    """Validate a document path.

    Args:
        v: Path string to validate
        required_dir: Directory the path must contain
        rejected_dir: Directory the path must not contain (None to skip check)
        doc_type: Document type name for error messages

    Returns:
        Resolved absolute path string

    Raises:
        ValueError: If validation fails
    """
    if required_dir not in v:
        msg = f"{doc_type.title()} document must be in {required_dir}/, got: {v}"
        raise ValueError(msg)

    if rejected_dir and rejected_dir in v:
        raise ValueError(f"Got plan document when {doc_type} expected: {v}")

    if not v.endswith(".md"):
        raise ValueError(f"Document must be markdown (.md): {v}")

    path = Path(v)
    if not path.exists():
        raise ValueError(f"{doc_type.title()} document does not exist: {v}")

    if not DATE_PATTERN.match(path.name):
        msg = f"{doc_type.title()} doc must start with YYYY-MM-DD: {path.name}"
        raise ValueError(msg)

    return str(path.resolve())


class ResearchDocPath(BaseModel):
    """Type-safe research document path with validation."""

    doc_type: Literal["research"] = "research"
    path: str

    @field_validator("path")
    @classmethod
    def validate_research_path(cls, v: str) -> str:
        """Validate path is a research document."""
        return _validate_doc_path(
            v, required_dir=RESEARCH_DIR, rejected_dir=PLANS_DIR, doc_type="research"
        )


class PlanDocPath(BaseModel):
    """Type-safe plan document path with validation."""

    doc_type: Literal["plan"] = "plan"
    path: str

    @field_validator("path")
    @classmethod
    def validate_plan_path(cls, v: str) -> str:
        """Validate path is a plan document."""
        return _validate_doc_path(
            v, required_dir=PLANS_DIR, rejected_dir=None, doc_type="plan"
        )


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
