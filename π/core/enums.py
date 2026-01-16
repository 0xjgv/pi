"""Core enums for π workflow configuration."""

from enum import StrEnum


class Tier(StrEnum):
    """Model tier levels."""

    LOW = "low"
    MED = "med"
    HIGH = "high"


class WorkflowStage(StrEnum):
    """Workflow stages for checkpoint tracking and tier mapping."""

    RESEARCH = "research"
    DESIGN = "design"
    EXECUTE = "execute"


class DocType(StrEnum):
    """Document types produced by workflow stages."""

    RESEARCH = "research"
    PLAN = "plan"


class Command(StrEnum):
    """Workflow stage commands."""

    RESEARCH_CODEBASE = "research_codebase"
    REVIEW_PLAN = "review_plan"
    CREATE_PLAN = "create_plan"
    IMPLEMENT_PLAN = "implement_plan"
    COMMIT = "commit"
    WRITE_CLAUDE_MD = "write_claude_md"  # Non-numbered command
