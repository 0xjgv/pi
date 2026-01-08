"""Factory functions for creating mock test data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from typing import Any


# ============================================================================
# DSPy LM Response Factories
# ============================================================================


@dataclass
class LMResponse:
    """Mock DSPy LM response structure."""

    rationale: str = "Test rationale"
    next_tool_name: str | None = None
    next_tool_args: str | None = None
    output: str = "Test output"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for mock return value."""
        result: dict[str, Any] = {
            "rationale": self.rationale,
            "output": self.output,
        }
        if self.next_tool_name:
            result["next_tool_name"] = self.next_tool_name
            result["next_tool_args"] = self.next_tool_args or "{}"
        return result


def create_lm_response(
    *,
    rationale: str = "Test rationale",
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    output: str = "Test output",
) -> LMResponse:
    """Create a mock LM response.

    Args:
        rationale: The reasoning for the action
        tool_name: Optional tool to call
        tool_args: Arguments for the tool
        output: Final output text

    Returns:
        LMResponse instance
    """
    return LMResponse(
        rationale=rationale,
        next_tool_name=tool_name,
        next_tool_args=json.dumps(tool_args) if tool_args else None,
        output=output,
    )


def create_research_response(*, doc_path: str = "/test/research.md") -> LMResponse:
    """Create mock response for research_codebase stage."""
    return create_lm_response(
        rationale="Researching the codebase to understand the structure",
        tool_name="research_codebase",
        tool_args={"query": "test research query"},
        output=f"Document saved at: {doc_path}",
    )


def create_plan_response(*, doc_path: str = "/test/plan.md") -> LMResponse:
    """Create mock response for create_plan stage."""
    return create_lm_response(
        rationale="Creating implementation plan based on research",
        tool_name="create_plan",
        tool_args={"query": "create plan"},
        output=f"Document saved at: {doc_path}",
    )


# ============================================================================
# Claude Agent SDK Response Factories
# ============================================================================


def create_result_message(
    *,
    result: str = "Test result",
    session_id: str = "test-session-123",
    num_turns: int = 3,
    duration_ms: int = 1000,
    duration_api_ms: int = 800,
    cost_usd: float = 0.01,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MagicMock:
    """Create a mock ResultMessage for workflow tests.

    Args:
        result: The result text from the agent
        session_id: Session ID for continuation
        num_turns: Number of conversation turns
        duration_ms: Total duration in milliseconds
        duration_api_ms: API call duration in milliseconds
        cost_usd: Total cost in USD
        input_tokens: Input token count
        output_tokens: Output token count

    Returns:
        MagicMock with spec=ResultMessage
    """
    from claude_agent_sdk.types import ResultMessage

    mock = MagicMock(spec=ResultMessage)
    mock.result = result
    mock.session_id = session_id
    mock.num_turns = num_turns
    mock.duration_ms = duration_ms
    mock.duration_api_ms = duration_api_ms
    mock.total_cost_usd = cost_usd
    mock.usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    return mock


def create_workflow_result(
    *,
    stage: str,
    doc_path: str | None = None,
    session_id: str = "workflow-session",
) -> MagicMock:
    """Create a mock ResultMessage for a specific workflow stage.

    Args:
        stage: Workflow stage name (research, plan, review, etc.)
        doc_path: Optional document path for stages that produce documents
        session_id: Session ID for continuation

    Returns:
        MagicMock with appropriate result text
    """
    result_text = f"{stage.capitalize()} completed successfully"
    if doc_path:
        result_text = f"Document saved at: {doc_path}\n{result_text}"

    return create_result_message(
        result=result_text,
        session_id=session_id,
    )
