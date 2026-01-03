"""Shared pytest fixtures for π test suite."""

import asyncio
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    # Cleanup after test
    for logger_name in ("π", "π.session", "π.workflow", "π.hooks"):
        logger = logging.getLogger(logger_name)
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
