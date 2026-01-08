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

# Suppress warnings from third-party libraries (litellm via dspy)
# Note: RuntimeWarning about 'close_litellm_async_clients' may still appear
# during interpreter shutdown - this is a known litellm issue and cannot be
# suppressed from within pytest as it occurs after the test session ends.
warnings.filterwarnings("ignore", category=ResourceWarning, module="litellm.*")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm.*")

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
    with patch("π.workflow.bridge.ClaudeSDKClient") as mock_class:
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
# DSPy Mocks
# ============================================================================


@pytest.fixture
def mock_dspy() -> Generator[MagicMock]:
    """Mock dspy module for CLI tests."""
    with patch("π.cli.dspy") as mock:
        mock_react = MagicMock()
        mock_react.return_value = MagicMock(output="Test output")
        mock.ReAct.return_value = mock_react
        yield mock


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
# Environment Fixtures
# ============================================================================


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear environment variables that affect tests."""
    monkeypatch.delenv("CLIPROXY_API_BASE", raising=False)
    monkeypatch.delenv("CLIPROXY_API_KEY", raising=False)


@pytest.fixture
def configured_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment variables for tests."""
    monkeypatch.setenv("CLIPROXY_API_BASE", "http://test:8317")
    monkeypatch.setenv("CLIPROXY_API_KEY", "test-key")


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
    for logger_name in ("π", "π.session", "π.workflow", "π.hooks"):
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
# DSPy LM Mocks
# ============================================================================
#
# Mock Architecture Overview:
# --------------------------
# This test suite uses a 3-layer mocking strategy to prevent API calls:
#
# Layer 1 (Lowest): DSPy LM Mock
#   - Patches dspy.LM at π.config to prevent any LM instantiation
#   - Use: mock_lm fixture (depends on clear_lm_cache)
#   - Tests: DSPy ReAct behavior, agent decision making
#
# Layer 2 (Middle): Claude SDK Mock
#   - Patches ClaudeSDKClient at π.workflow.bridge
#   - Use: mock_claude_client, mock_claude_client_with_responses fixtures
#   - Tests: Workflow bridge, message handling, session management
#
# Layer 3 (Highest): Workflow Stage Mock
#   - Patches workflow functions directly (research_codebase, create_plan, etc.)
#   - Use: mock_workflow_stages fixture
#   - Tests: CLI, high-level integration, stage orchestration
#
# Choose the layer that matches your test scope. Lower layers provide more
# realistic behavior but require more setup. Higher layers are simpler but
# bypass more production code.
# ============================================================================


@pytest.fixture
def mock_lm_response() -> dict[str, str]:
    """Default LM response for DSPy completions."""
    return {
        "rationale": "Test rationale for action selection",
        "next_tool_name": "research_codebase",
        "next_tool_args": '{"query": "test query"}',
        "output": "Test output from mock LM",
    }


@pytest.fixture
def clear_lm_cache():
    """Clear LRU cache on get_lm before and after tests.

    This fixture is a dependency of mock_lm to ensure the cache is always
    cleared before patching. Can also be used independently for tests that
    modify LM configuration.

    Note: The get_lm() function uses @lru_cache(maxsize=6), so cache must
    be cleared before mocking to prevent test pollution from cached real LMs.
    """
    from π.config import get_lm

    get_lm.cache_clear()
    yield
    get_lm.cache_clear()


@pytest.fixture
def mock_lm(
    clear_lm_cache,  # Explicit dependency ensures cache is cleared
    mock_lm_response: dict[str, str],
) -> Generator[MagicMock]:
    """Mock dspy.LM to prevent API calls.

    This fixture patches get_lm() to return a mock LM that:
    - Returns predefined completions
    - Tracks call history for assertions
    - Simulates streaming behavior

    Note: Depends on clear_lm_cache to ensure LRU cache is cleared before
    patching. This prevents test pollution from cached LM instances.
    """
    with patch("π.core.models.dspy.LM") as mock_class:
        mock_instance = MagicMock()

        # Mock the __call__ method to return completions
        mock_instance.return_value = [mock_lm_response["output"]]

        # Mock inspect for DSPy internals
        mock_instance.inspect_history.return_value = []

        mock_class.return_value = mock_instance
        yield mock_instance


# ============================================================================
# Enhanced Claude Agent SDK Mocks (Layer 2)
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
        with patch("π.workflow.bridge.ClaudeSDKClient") as mock_class:
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
# Workflow Stage Fixtures (Layer 3)
# ============================================================================


@pytest.fixture
def fresh_execution_context():
    """Create a fresh ExecutionContext for workflow tests.

    This fixture:
    - Creates a new ExecutionContext
    - Sets it as the current context
    - Cleans up after the test (including closing event loop)
    """
    from π.workflow import ExecutionContext
    from π.workflow.bridge import _ctx

    ctx = ExecutionContext()
    token = _ctx.set(ctx)
    yield ctx
    # Close event loop if one was created to avoid ResourceWarning
    if ctx.event_loop is not None and not ctx.event_loop.is_closed():
        ctx.event_loop.close()
    _ctx.reset(token)


@pytest.fixture
def execution_context_with_session(
    fresh_execution_context,
):
    """Create an ExecutionContext with pre-populated session IDs.

    Useful for testing session resumption scenarios.
    """
    from π.workflow import Command

    for cmd in Command:
        fresh_execution_context.session_ids[cmd] = f"session-{cmd.value}"
    return fresh_execution_context


@pytest.fixture
def execution_context_with_docs(
    fresh_execution_context,
    tmp_path: Path,
):
    """Create an ExecutionContext with pre-populated document paths.

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
    fresh_execution_context.extracted_paths["research"] = {str(research_doc)}
    fresh_execution_context.extracted_paths["plan"] = {str(plan_doc)}
    fresh_execution_context.extracted_results = {}

    return fresh_execution_context


@pytest.fixture
def mock_workflow_stages():
    """Mock all workflow stage functions.

    Returns a dict mapping stage names to their mocks for configuration.

    Note on @workflow_tool decorated functions:
    The workflow functions (research_codebase, create_plan, etc.) are decorated
    with @workflow_tool which uses @functools.wraps(func). When we patch at
    π.workflow.tools.research_codebase, we're patching the DECORATED function
    (the wrapper), not the inner function. This is correct behavior because:

    1. @wraps preserves the function identity at the module level
    2. Callers import and call the decorated version
    3. The patch intercepts calls BEFORE the decorator's wrapper executes
    4. This means session management, timing, and error handling are bypassed

    If you need to test the decorator's behavior, mock at a lower level
    (e.g., mock execute_claude_task instead).
    """
    stages = {
        "research": "π.workflow.tools.research_codebase",
        "plan": "π.workflow.tools.create_plan",
        "review": "π.workflow.tools.review_plan",
        "iterate": "π.workflow.tools.iterate_plan",
        "implement": "π.workflow.tools.implement_plan",
        "commit": "π.workflow.tools.commit_changes",
    }

    mocks = {}
    patches = []

    for name, path in stages.items():
        patcher = patch(path)
        mock = patcher.start()
        mock.return_value = f"[COMPLETE] {name.capitalize()} stage completed"
        mocks[name] = mock
        patches.append(patcher)

    yield mocks

    for patcher in patches:
        patcher.stop()


@pytest.fixture
def mock_rpi_workflow_full():
    """Mock StagedWorkflow with complete stage simulation.

    Simulates a full workflow execution with all stages returning success.
    Note: Must patch at π.cli.main.StagedWorkflow since that's where the CLI imports it.
    """
    with patch("π.cli.main.StagedWorkflow") as mock_class:
        mock_instance = MagicMock()

        # Configure return value
        mock_result = MagicMock()
        mock_result.status = "success"
        mock_result.research_doc_path = "/tmp/research.md"
        mock_result.plan_doc_path = "/tmp/plan.md"
        mock_result.files_changed = ["test.py"]
        mock_result.commit_hash = "abc1234"
        mock_instance.return_value = mock_result

        mock_class.return_value = mock_instance
        yield mock_instance
