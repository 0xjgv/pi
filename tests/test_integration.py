"""Integration tests for π CLI workflows."""

from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from claude_agent_sdk.types import HookContext, HookInput, ResultMessage

from π.cli import main


class TestFullWorkflowIntegration:
    """Integration tests for complete CLI workflows."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create an isolated CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_claude_responses(self) -> Generator[AsyncMock, None, None]:
        """Set up complete mock for Claude SDK."""
        with patch("π.workflow.bridge.ClaudeSDKClient") as mock_client_class:
            # Create async mock client
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Mock result message
            result_msg = MagicMock(spec=ResultMessage)
            result_msg.result = "Integration test completed"
            result_msg.session_id = "int-test-session"
            result_msg.num_turns = 2
            result_msg.duration_ms = 500
            result_msg.duration_api_ms = 400
            result_msg.total_cost_usd = 0.01
            result_msg.usage = {}

            # Set up async iterator
            async def response_iterator():
                yield result_msg

            mock_client.receive_response.return_value = response_iterator()

            yield mock_client

    @pytest.fixture
    def mock_dspy_agent(self) -> Generator[MagicMock, None, None]:
        """Mock DSPy ReAct agent."""
        with patch("π.cli.dspy") as mock_dspy:
            mock_agent = MagicMock()
            mock_agent.return_value = MagicMock(output="DSPy agent output")
            mock_dspy.ReAct.return_value = mock_agent
            yield mock_dspy

    def test_cli_initializes_and_runs(
        self,
        runner: CliRunner,
        mock_dspy_agent: MagicMock,  # noqa: ARG002
        mock_claude_responses: AsyncMock,  # noqa: ARG002
    ):
        """CLI should initialize DSPy and run agent successfully."""
        from π.workflow import ExecutionMode

        with patch("π.cli.classify_objective", return_value=ExecutionMode.SIMPLE):
            result = runner.invoke(main, ["test objective", "-t", "low"])

        assert result.exit_code == 0
        assert "[Simple Mode]" in result.output
        assert "Final Answer:" in result.output

    def test_agent_options_flow_to_workflow(
        self,
        runner: CliRunner,
        mock_dspy_agent: MagicMock,  # noqa: ARG002
        mock_claude_responses: AsyncMock,  # noqa: ARG002
    ):
        """Agent options should be correctly configured."""
        from π.workflow import ExecutionMode

        with (
            patch("π.cli.classify_objective", return_value=ExecutionMode.SIMPLE),
            patch("π.workflow.bridge._get_agent_options") as mock_opts,
        ):
            from claude_agent_sdk import ClaudeAgentOptions

            mock_opts.return_value = ClaudeAgentOptions(
                permission_mode="acceptEdits",
                allowed_tools=["Bash", "Read"],
            )

            result = runner.invoke(main, ["test"])

            assert result.exit_code == 0

    def test_error_handling_propagates(
        self,
        runner: CliRunner,
        mock_dspy_agent: MagicMock,
    ):
        """Errors should be handled gracefully."""
        mock_dspy_agent.ReAct.return_value.side_effect = Exception("Agent error")

        result = runner.invoke(main, ["test"])

        # Should not crash, but may show error
        assert result.exit_code != 0 or "error" in result.output.lower()


class TestHookIntegration:
    """Integration tests for hook system."""

    @pytest.fixture
    def project_with_python(self, tmp_path: Path) -> Path:
        """Create a Python project structure."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hello')\n")
        return tmp_path

    def test_check_file_format_integrates_with_registry(
        self, project_with_python: Path
    ):
        """check_file_format should use registry to find checker."""
        from π.hooks.registry import get_checker

        # Verify Python checker is registered
        checker = get_checker(".py")
        assert checker is not None

        # Test that file would be recognized
        python_file = project_with_python / "src" / "main.py"
        assert python_file.suffix == ".py"

    @pytest.mark.asyncio
    async def test_bash_command_hook_blocks_dangerous(self):
        """Bash command hook should block dangerous commands."""
        from π.hooks import check_bash_command

        dangerous_input = cast(
            HookInput,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
            },
        )
        context = HookContext(signal=None)

        result = await check_bash_command(dangerous_input, None, context)

        hook_output = result.get("hookSpecificOutput")
        assert hook_output is not None
        assert hook_output.get("permissionDecision") == "deny"

    @pytest.mark.asyncio
    async def test_bash_command_hook_allows_safe(self):
        """Bash command hook should allow safe commands."""
        from π.hooks import check_bash_command

        safe_input = cast(
            HookInput,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls -la"},
            },
        )
        context = HookContext(signal=None)

        result = await check_bash_command(safe_input, None, context)

        assert result == {}


class TestSessionStateIntegration:
    """Integration tests for session state management."""

    def test_session_persists_across_workflow_calls(self):
        """Session state should persist across multiple workflow calls."""
        from π.workflow import Command, WorkflowSession
        from π.workflow.bridge import _get_session, _session_var

        # Clear any existing session
        try:
            _session_var.set(WorkflowSession())
        except LookupError:
            pass

        session = _get_session()
        session.set_session_id(Command.RESEARCH_CODEBASE, "test-session")

        # Retrieve again - should be same session
        retrieved = _get_session()
        assert retrieved.get_session_id(Command.RESEARCH_CODEBASE) == "test-session"

    def test_command_map_built_correctly(self):
        """Command map should be built from actual command files."""
        from π.workflow import COMMAND_MAP, Command

        # Should have entries for commands that have files
        # (depends on actual .claude/commands/ content)
        assert isinstance(COMMAND_MAP, dict)

        # All values should be slash commands
        for cmd, value in COMMAND_MAP.items():
            assert isinstance(cmd, Command)
            assert value.startswith("/")


class TestLogCleanupIntegration:
    """Integration tests for log cleanup functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create an isolated CLI runner."""
        return CliRunner()

    def test_cli_cleans_old_app_logs_on_startup(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """CLI should cleanup old application logs at startup."""
        from datetime import datetime, timedelta

        from π.workflow import ExecutionMode

        # Create test log directory
        logs_dir = tmp_path / ".π" / "logs"
        logs_dir.mkdir(parents=True)

        # Create old log files (10 days ago)
        old_date = datetime.now() - timedelta(days=10)
        old_log = logs_dir / f"{old_date.strftime('%Y-%m-%d')}-10:00.log"
        old_log.write_text("old log content")

        # Create recent log file (3 days ago)
        recent_date = datetime.now() - timedelta(days=3)
        recent_log = logs_dir / f"{recent_date.strftime('%Y-%m-%d')}-10:00.log"
        recent_log.write_text("recent log content")

        # Change to test directory
        monkeypatch.chdir(tmp_path)

        # Mock the agent execution to avoid actual agent run
        with (
            patch("π.cli.classify_objective", return_value=ExecutionMode.SIMPLE),
            patch("π.cli.dspy") as mock_dspy,
        ):
            mock_agent = MagicMock()
            mock_agent.return_value = MagicMock(output="Test output")
            mock_dspy.ReAct.return_value = mock_agent

            result = runner.invoke(main, ["test objective"])

        # Verify cleanup occurred
        assert result.exit_code == 0
        assert not old_log.exists(), "Old log should be deleted"
        assert recent_log.exists(), "Recent log should be preserved"

    def test_hook_logs_cleaned_on_direct_call(
        self,
        log_dir: Path,
    ):
        """Hook cleanup function should delete old logs when called directly."""
        from datetime import datetime, timedelta

        from π.hooks.logging import cleanup_old_hook_logs

        # Create old hook log file (40 days ago)
        old_date = datetime.now() - timedelta(days=40)
        old_hook_log = log_dir / f"{old_date.strftime('%Y-%m-%d')}-hooks.log"
        old_hook_log.write_text("old hook log content")

        # Create recent hook log file (15 days ago)
        recent_date = datetime.now() - timedelta(days=15)
        recent_hook_log = log_dir / f"{recent_date.strftime('%Y-%m-%d')}-hooks.log"
        recent_hook_log.write_text("recent hook log content")

        # Call cleanup directly
        deleted = cleanup_old_hook_logs(retention_days=30)

        # Verify cleanup occurred
        assert deleted == 1, "Should have deleted 1 file"
        assert not old_hook_log.exists(), "Old hook log should be deleted"
        assert recent_hook_log.exists(), "Recent hook log should be preserved"

    def test_cleanup_creates_no_errors_with_empty_dirs(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Cleanup should handle empty log directories gracefully."""
        from π.workflow import ExecutionMode

        # Create empty log directory
        logs_dir = tmp_path / ".π" / "logs"
        logs_dir.mkdir(parents=True)

        # Change to test directory
        monkeypatch.chdir(tmp_path)

        # Mock the agent execution
        with (
            patch("π.cli.classify_objective", return_value=ExecutionMode.SIMPLE),
            patch("π.cli.dspy") as mock_dspy,
        ):
            mock_agent = MagicMock()
            mock_agent.return_value = MagicMock(output="Test output")
            mock_dspy.ReAct.return_value = mock_agent

            result = runner.invoke(main, ["test objective"])

        # Should complete successfully with no errors
        assert result.exit_code == 0
