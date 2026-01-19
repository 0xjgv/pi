"""Factory functions for creating mock test data."""

from unittest.mock import MagicMock

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
