# π Test Suite

## Overview

This test suite is designed to run **without any API token usage**. All external dependencies (DSPy LM, Claude SDK) are mocked at appropriate layers.

## Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run tests explicitly without API (CI mode)
make test-no-api

# Run only tests marked as no_api
make test-markers
```

## Test Architecture

### Mock Layers

1. **DSPy LM Layer** (`mock_lm` fixture)
   - Mocks `dspy.LM` to prevent API calls
   - Use for testing DSPy ReAct agent behavior

2. **Claude SDK Layer** (`mock_claude_client` fixtures)
   - Mocks `ClaudeSDKClient` for workflow tests
   - Use for testing bridge and workflow stages

3. **Workflow Layer** (`mock_workflow_stages` fixture)
   - Mocks individual workflow functions
   - Use for testing CLI and high-level integration

### Fixture Hierarchy

```
conftest.py
├── Path Fixtures (tmp_path based)
│   ├── project_root
│   ├── python_file
│   └── typescript_project
├── Claude SDK Mocks (Layer 2)
│   ├── mock_claude_client          # Basic client mock
│   ├── mock_result_message         # ResultMessage factory
│   ├── mock_assistant_message      # AssistantMessage factory
│   ├── mock_tool_result            # ToolResultBlock factory
│   └── mock_claude_client_with_responses  # Configurable response sequence
├── DSPy Mocks (Layer 1)
│   ├── mock_dspy                   # Patches π.cli.dspy
│   ├── mock_lm_response            # Default LM response dict
│   ├── clear_lm_cache              # Clears @lru_cache on get_lm
│   └── mock_lm                     # Patches dspy.LM, depends on clear_lm_cache
├── Subprocess Mocks
│   ├── mock_subprocess_success
│   └── mock_subprocess_failure
├── Environment Fixtures
│   ├── clean_env                   # Removes CLIPROXY_* vars
│   └── configured_env              # Sets test CLIPROXY_* vars
├── Workflow Context (Layer 3)
│   ├── fresh_execution_context     # Clean context with _ctx.set()
│   ├── execution_context_with_session  # Pre-populated session IDs
│   └── execution_context_with_docs # Pre-populated doc paths + temp files
├── Workflow Stage Mocks (Layer 3)
│   ├── mock_workflow_stages        # Patches all 6 workflow functions
│   └── mock_rpi_workflow_full      # Mocks RPIWorkflow class
├── Other Fixtures
│   ├── mock_console
│   ├── mock_spinner
│   └── clean_registry
└── Autouse Fixtures
    └── cleanup_logging_handlers
```

### Response Factories

Use factories from `tests/factories.py` for consistent mock data:

```python
from tests.factories import (
    create_lm_response,
    create_result_message,
    create_workflow_result,
)

# Create a mock LM response
response = create_lm_response(
    rationale="Testing the feature",
    tool_name="research_codebase",
    output="Research complete",
)

# Create a mock ResultMessage
result = create_result_message(
    result="Test completed",
    session_id="test-session",
    cost_usd=0.01,
)
```

## Writing New Tests

### Class-Based Organization

```python
class TestFeatureName:
    """Tests for feature description."""

    @pytest.fixture(autouse=True)
    def setup(self, mock_lm, clean_env):
        """Set up common mocks for all tests in this class."""
        self.mock_lm = mock_lm

    def test_specific_behavior(self):
        """Should do something specific."""
        # Arrange
        # Act
        # Assert
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_function(self, mock_claude_client):
    """Should handle async operations."""
    result = await some_async_function()
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("input1", "expected1"),
    ("input2", "expected2"),
])
def test_multiple_cases(self, input, expected):
    """Should handle various inputs."""
    assert process(input) == expected
```

## Common Patterns

### Testing Without API

```python
def test_feature_no_api(
    self,
    mock_lm,           # Prevents DSPy API calls
    mock_claude_client, # Prevents Claude SDK calls
    clean_env,          # Removes API env vars
):
    """Test should work without any API access."""
    result = some_function()
    assert result is not None
```

### Testing Workflow Stages

```python
def test_workflow_stage(
    self,
    mock_execute_task,        # Mock the bridge
    fresh_execution_context,  # Clean context
):
    """Test individual workflow stage."""
    mock_execute_task.return_value = ("Result", "session-id")

    result = workflow_function(query="test")

    assert "[COMPLETE]" in result or "[IN_PROGRESS]" in result
```

### Testing Session Management

```python
def test_session_resumption(
    self,
    execution_context_with_session,
    mock_execute_task,
):
    """Test that sessions are resumed correctly."""
    result = workflow_function(query="continue")

    call_kwargs = mock_execute_task.call_args.kwargs
    assert call_kwargs["session_id"] is not None
```

## Troubleshooting

### Tests Failing with API Errors

If you see `CLIPROXY_API_KEY required` errors:

1. Ensure you're using the appropriate mock fixture
2. Check that `clean_env` fixture is applied
3. Verify LRU cache is cleared with `clear_lm_cache`

### Context Variable Leaks

If tests affect each other:

1. Use `fresh_execution_context` fixture
2. Add `autouse=True` cleanup fixture if needed
3. Clear context in test teardown

### Async Test Timeouts

If async tests hang:

1. Ensure `asyncio_mode = "auto"` in pyproject.toml
2. Use `event_loop` fixture for custom loops
3. Check that async mocks use `AsyncMock`
