from typing import Literal

from pydantic import BaseModel, Field


class StageOutput(BaseModel):
    """Structured output for stage execution."""

    status: Literal["complete", "questions", "error"] = Field(
        description="The status of the stage"
    )
    error_message: str | None = Field(
        description="The error message from the stage", default=None
    )
    output_file: str | None = Field(
        description="The path to the output file", default=None
    )
    questions: list[str] = Field(description="The questions from the stage", default=[])
    summary: str = Field(description="The summary of the stage")


class StageResult(BaseModel):
    """Captures the outcome of a stage execution."""

    stage: str = Field(description="The name of the stage")
    status: Literal["complete", "questions", "error"] = Field(
        description="The status of the stage"
    )
    output_file: str | None = Field(description="The path to the output file")
    response: str | None = Field(description="The response from the stage")
    questions: list[str] = Field(description="The questions from the stage")


class SupervisorDecision(BaseModel):
    """Structured output for supervisor review."""

    approved: bool = Field(description="Whether the stage output is approved")
    feedback: str = Field(
        description="Rationale for approval or specific revision instructions"
    )
