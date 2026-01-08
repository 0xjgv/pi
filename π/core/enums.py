"""Core enums for π workflow configuration."""

from enum import StrEnum


class Provider(StrEnum):
    """LLM provider identifiers."""

    Claude = "claude"
    Antigravity = "antigravity"


class Tier(StrEnum):
    """Model tier levels."""

    LOW = "low"
    MED = "med"
    HIGH = "high"
    ULTRA = "ultra"


class Stage(StrEnum):
    """Workflow stages."""

    RESEARCH_CODEBASE = "research_codebase"
    PLAN = "plan"
    REVIEW_PLAN = "review_plan"
    ITERATE_PLAN = "iterate_plan"
    IMPLEMENT_PLAN = "implement_plan"
    COMMIT = "commit"
