"""Root test fixtures shared across unit and integration tests.

Module-specific fixtures are in:
- tests/unit/conftest.py (unit test documentation)
- tests/integration/conftest.py (integration test documentation)

This file contains fixtures used by both test categories.
"""

import asyncio
import logging
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from π.core.enums import DocType

# Suppress warnings from third-party libraries
warnings.filterwarnings("ignore", category=ResourceWarning, module="claude_agent_sdk.*")

# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a mock project structure with pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.fixture
def python_file(tmp_path: Path) -> Path:
    """Create a temporary Python file for testing."""
    file = tmp_path / "test_file.py"
    file.write_text("print('hello')\n")
    return file


@pytest.fixture
def typescript_project(tmp_path: Path) -> Path:
    """Create a mock TypeScript project structure."""
    (tmp_path / "package.json").write_text('{"name": "test"}')
    (tmp_path / "eslint.config.js").write_text("module.exports = {};")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("console.log('hello');")
    return tmp_path


# ============================================================================
# Claude Agent SDK Mocks
# ============================================================================


@pytest.fixture
def mock_claude_client() -> Generator[MagicMock]:
    """Mock ClaudeSDKClient for workflow tests."""
    with patch("π.bridge.session.ClaudeSDKClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value.__aenter__.return_value = mock_client
        mock_class.return_value.__aexit__.return_value = None
        yield mock_client


@pytest.fixture
def mock_result_message() -> MagicMock:
    """Create a mock ResultMessage for workflow tests."""
    from claude_agent_sdk.types import ResultMessage

    mock = MagicMock(spec=ResultMessage)
    mock.result = "Test result"
    mock.session_id = "test-session-123"
    mock.num_turns = 3
    mock.duration_ms = 1000
    mock.duration_api_ms = 800
    mock.total_cost_usd = 0.01
    mock.usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    return mock


@pytest.fixture
def mock_hook_input() -> dict[str, Any]:
    """Create a mock HookInput for hook tests."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
    }


# ============================================================================
# Subprocess Mocks
# ============================================================================


@pytest.fixture
def mock_subprocess_success() -> Generator[MagicMock]:
    """Mock subprocess.run with successful exit."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )
        yield mock


@pytest.fixture
def mock_subprocess_failure() -> Generator[MagicMock]:
    """Mock subprocess.run with failure exit."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: lint failed",
        )
        yield mock


# ============================================================================
# Logging Fixtures
# ============================================================================


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect hook logs to temporary directory."""
    log_path = tmp_path / ".claude" / "hook-logs"
    log_path.mkdir(parents=True)
    monkeypatch.setattr("π.hooks.logging._LOG_DIR", log_path)
    return log_path


# ============================================================================
# Registry Isolation
# ============================================================================


@pytest.fixture
def clean_registry() -> Generator[None]:
    """Isolate registry state between tests."""
    from π.hooks import registry

    original = registry._registry.copy()
    registry._registry.clear()
    yield
    registry._registry.clear()
    registry._registry.update(original)


# ============================================================================
# Async Event Loop Fixture
# ============================================================================


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Logging Cleanup (autouse)
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_logging_handlers():
    """Clean up logging handlers after each test to prevent test pollution.

    This prevents tests that call setup_logging() from polluting other tests
    with FileHandlers that write to real log files.
    """
    yield
    # Cleanup after test - close handlers before clearing to avoid ResourceWarning
    for logger_name in ("π", "π.session", "π.bridge", "π.hooks"):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            handler.close()
        logger.handlers.clear()


# ============================================================================
# Console & Spinner Mocks (for permissions/hitl tests)
# ============================================================================


@pytest.fixture
def mock_console() -> Generator[MagicMock]:
    """Mock Rich Console for HITL tests."""
    with patch("π.support.permissions.console") as mock:
        mock.input.return_value = "test response"
        yield mock


@pytest.fixture
def mock_spinner() -> Generator[MagicMock]:
    """Mock spinner status for permissions tests."""
    with patch("π.support.permissions.get_current_status") as mock_get:
        mock_status = MagicMock()
        mock_get.return_value = mock_status
        yield mock_status


# ============================================================================
# Enhanced Claude Agent SDK Mocks
# ============================================================================


@pytest.fixture
def mock_assistant_message():
    """Factory for creating mock AssistantMessage instances."""
    from claude_agent_sdk.types import AssistantMessage, TextBlock, ToolUseBlock

    def _create(
        *,
        text: str = "Assistant response",
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
    ) -> MagicMock:
        mock = MagicMock(spec=AssistantMessage)
        blocks = []

        if text:
            text_block = MagicMock(spec=TextBlock)
            text_block.text = text
            blocks.append(text_block)

        if tool_name:
            tool_block = MagicMock(spec=ToolUseBlock)
            tool_block.name = tool_name
            tool_block.input = tool_input or {}
            blocks.append(tool_block)

        mock.content = blocks
        return mock

    return _create


@pytest.fixture
def mock_tool_result():
    """Factory for creating mock ToolResultBlock instances."""
    from claude_agent_sdk.types import ToolResultBlock

    def _create(
        *,
        content: str = "Tool result",
        is_error: bool = False,
    ) -> MagicMock:
        mock = MagicMock(spec=ToolResultBlock)
        mock.content = content
        mock.is_error = is_error
        return mock

    return _create


@pytest.fixture
def mock_claude_client_with_responses():
    """Create a mock Claude client with configurable response sequence.

    Usage:
        def test_example(mock_claude_client_with_responses, mock_result_message):
            messages = [mock_result_message]
            with mock_claude_client_with_responses(messages) as client:
                # client.receive_response() will yield messages in order
                ...
    """
    from contextlib import contextmanager

    @contextmanager
    def _create(messages: list[MagicMock]):
        with patch("π.bridge.session.ClaudeSDKClient") as mock_class:
            mock_client = AsyncMock()
            mock_class.return_value.__aenter__.return_value = mock_client
            mock_class.return_value.__aexit__.return_value = None

            async def response_iterator():
                for msg in messages:
                    yield msg

            mock_client.receive_response.return_value = response_iterator()
            yield mock_client

    return _create


# ============================================================================
# Workflow Context Fixtures
# ============================================================================


@pytest.fixture
def fresh_workflow_context():
    """Create a fresh WorkflowContext for workflow tests.

    This fixture:
    - Creates a new WorkflowContext
    - Sets it as the current context
    - Cleans up after the test
    """
    from π.workflow.context import get_workflow_ctx, reset_workflow_ctx

    reset_workflow_ctx()
    ctx = get_workflow_ctx()
    yield ctx
    reset_workflow_ctx()


@pytest.fixture
def workflow_context_with_docs(
    fresh_workflow_context,
    tmp_path: Path,
):
    """Create a WorkflowContext with pre-populated document paths.

    Creates actual temporary files for validation tests.
    """
    # Create research document
    research_dir = tmp_path / "thoughts" / "shared" / "research"
    research_dir.mkdir(parents=True)
    research_doc = research_dir / "2026-01-05-test-research.md"
    research_doc.write_text("# Test Research\n\nResearch content.")

    # Create plan document
    plan_dir = tmp_path / "thoughts" / "shared" / "plans"
    plan_dir.mkdir(parents=True)
    plan_doc = plan_dir / "2026-01-05-test-plan.md"
    plan_doc.write_text("# Test Plan\n\nPlan content.")

    # Store paths
    fresh_workflow_context.doc_paths[DocType.RESEARCH] = str(research_doc)
    fresh_workflow_context.doc_paths[DocType.PLAN] = str(plan_doc)

    return fresh_workflow_context


@pytest.fixture
def mock_run_claude_session():
    """Mock run_claude_session to avoid API calls.

    Returns:
        A mock that can be configured with side_effect for different return values.
        Default returns ("Result", "session-123", "/path/doc.md", ["file.py"]).
    """
    with patch("π.workflow.tools.run_claude_session") as mock:

        async def default_impl(**_kwargs):
            return ("Result", "session-123", "/path/doc.md", ["file.py"])

        mock.side_effect = default_impl
        yield mock
