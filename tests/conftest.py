"""Shared pytest fixtures for π test suite."""

import asyncio
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Logging Fixtures
# ============================================================================


@pytest.fixture
def clean_logging() -> Generator[None, None, None]:
    """Reset logging state before and after tests."""
    # Store original state
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level
    pi_logger = logging.getLogger("π")
    original_pi_level = pi_logger.level
    original_pi_handlers = pi_logger.handlers[:]

    # Clean state for test
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.setLevel(logging.WARNING)
    pi_logger.handlers.clear()

    yield

    # Restore original state
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    for handler in original_handlers:
        logging.root.addHandler(handler)
    logging.root.setLevel(original_level)

    pi_logger.handlers = original_pi_handlers
    pi_logger.setLevel(original_pi_level)


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect hook logs to temporary directory."""
    log_path = tmp_path / ".claude" / "hook-logs"
    log_path.mkdir(parents=True)
    monkeypatch.setattr("π.hooks.logging._LOG_DIR", log_path)
    return log_path


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
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project structure with common files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").touch()
    return tmp_path


@pytest.fixture
def temp_command_dir(tmp_path: Path) -> Path:
    """Create a temporary command directory with sample commands."""
    cmd_dir = tmp_path / ".claude" / "commands"
    cmd_dir.mkdir(parents=True)

    (cmd_dir / "0_clarify.md").write_text("# Clarify\nClarify the task.")
    (cmd_dir / "1_research_codebase.md").write_text(
        "# Research\nResearch the codebase."
    )
    (cmd_dir / "2_create_plan.md").write_text("# Plan\nCreate a plan.")
    (cmd_dir / "3_implement_plan.md").write_text("# Implement\nImplement the plan.")

    return cmd_dir


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
def mock_claude_client() -> Generator[MagicMock, None, None]:
    """Mock ClaudeSDKClient for workflow tests."""
    with patch("π.workflow.ClaudeSDKClient") as mock_class:
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


@pytest.fixture
def mock_console(mocker: MagicMock) -> MagicMock:
    """Mock the Rich console to prevent output during tests."""
    return mocker.patch("π.hooks.utils.console")


# ============================================================================
# DSPy Mocks
# ============================================================================


@pytest.fixture
def mock_dspy() -> Generator[MagicMock, None, None]:
    """Mock dspy module for CLI tests."""
    with patch("π.cli.dspy") as mock:
        mock_react = MagicMock()
        mock_react.return_value = MagicMock(output="Test output")
        mock.ReAct.return_value = mock_react
        yield mock


@pytest.fixture
def mock_dspy_configure() -> Generator[MagicMock, None, None]:
    """Mock dspy.configure for config tests."""
    with patch("π.config.dspy") as mock:
        yield mock


# ============================================================================
# Subprocess Mocks
# ============================================================================


@pytest.fixture
def mock_subprocess_success() -> Generator[MagicMock, None, None]:
    """Mock subprocess.run with successful exit."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )
        yield mock


@pytest.fixture
def mock_subprocess_failure() -> Generator[MagicMock, None, None]:
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
# Registry Isolation
# ============================================================================


@pytest.fixture
def clean_registry() -> Generator[None, None, None]:
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
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
