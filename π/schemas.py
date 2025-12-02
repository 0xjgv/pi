from typing import Literal

from pydantic import BaseModel, Field


class StageOutput(BaseModel):
    """Structured output for stage execution."""

    status: Literal["complete", "questions", "error"]
    error_message: str | None = None
    output_file: str | None = None
    questions: list[str] = []
    summary: str


class SupervisorDecision(BaseModel):
    """Structured output for supervisor review."""

    approved: bool = Field(description="Whether the stage output is approved")
    feedback: str = Field(
        description="Rationale for approval or specific revision instructions"
    )
