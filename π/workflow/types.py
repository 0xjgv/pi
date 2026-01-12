"""Type-safe document paths and stage result models."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

# Directory constants
RESEARCH_DIR = "thoughts/shared/research"
PLANS_DIR = "thoughts/shared/plans"

# Document type discriminator
DocType = Literal["plan", "research"]

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


class _DocPath(BaseModel):
    """Base class for document path validation."""

    _required_dir: ClassVar[str]
    _rejected_dir: ClassVar[str | None] = None
    _doc_type: ClassVar[str]
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path using class-level configuration."""
        return _validate_doc_path(
            v,
            required_dir=cls._required_dir,
            rejected_dir=cls._rejected_dir,
            doc_type=cls._doc_type,
        )


class ResearchDocPath(_DocPath):
    """Type-safe research document path with validation."""

    _required_dir: ClassVar[str] = RESEARCH_DIR
    _rejected_dir: ClassVar[str | None] = PLANS_DIR
    _doc_type: ClassVar[str] = "research"
    doc_type: Literal["research"] = "research"


class PlanDocPath(_DocPath):
    """Type-safe plan document path with validation."""

    _required_dir: ClassVar[str] = PLANS_DIR
    _doc_type: ClassVar[str] = "plan"
    doc_type: Literal["plan"] = "plan"


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
