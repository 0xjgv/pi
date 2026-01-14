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


class WorkflowStage(StrEnum):
    """Workflow stages for checkpoint tracking and tier mapping."""

    RESEARCH = "research"
    DESIGN = "design"
    EXECUTE = "execute"
