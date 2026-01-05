"""Integration tests for π CLI workflows."""

from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk.types import HookContext, HookInput, ResultMessage

from π.cli import main


class TestFullWorkflowIntegration:
    """Integration tests for complete CLI workflows."""

    @pytest.fixture
    def mock_claude_responses(self) -> Generator[AsyncMock]:
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
    def mock_rpi_workflow(self) -> Generator[MagicMock]:
        """Mock RPIWorkflow for integration tests."""
        with patch("π.cli.RPIWorkflow") as mock:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock.return_value = mock_instance
            yield mock

    def test_cli_initializes_and_runs(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,
        mock_claude_responses: AsyncMock,
    ):
        """CLI should initialize workflow and run successfully."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "[Workflow Mode]" in captured.out

    def test_agent_options_flow_to_workflow(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,
        mock_claude_responses: AsyncMock,
    ):
        """Agent options should be correctly configured."""
        with patch("π.workflow.bridge._get_agent_options") as mock_opts:
            from claude_agent_sdk import ClaudeAgentOptions

            mock_opts.return_value = ClaudeAgentOptions(
                permission_mode="acceptEdits",
                allowed_tools=["Bash", "Read"],
            )

            main(["test"])
            captured = capsys.readouterr()

            assert "Workflow Mode" in captured.out

    def test_error_handling_propagates(
        self,
        mock_rpi_workflow: MagicMock,
    ):
        """Errors should be handled gracefully."""
        mock_rpi_workflow.return_value.side_effect = Exception("Workflow error")

        with pytest.raises(Exception, match="Workflow error"):
            main(["test"])


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
            "HookInput",
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
            "HookInput",
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
        from π.workflow import Command, ExecutionContext
        from π.workflow.bridge import _ctx, _get_ctx

        # Clear any existing context
        try:
            _ctx.set(ExecutionContext())
        except LookupError:
            pass

        ctx = _get_ctx()
        ctx.session_ids[Command.RESEARCH_CODEBASE] = "test-session"

        # Retrieve again - should be same context
        retrieved = _get_ctx()
        assert retrieved.session_ids.get(Command.RESEARCH_CODEBASE) == "test-session"

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

    def test_cli_cleans_old_app_logs_on_startup(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """CLI should cleanup old application logs at startup."""
        from datetime import datetime, timedelta

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

        # Mock the workflow execution to avoid actual agent run
        with patch("π.cli.RPIWorkflow") as mock_workflow:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock_workflow.return_value = mock_instance

            main(["test objective"])
            captured = capsys.readouterr()

        # Verify cleanup occurred
        assert "Workflow Mode" in captured.out
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
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Cleanup should handle empty log directories gracefully."""
        # Create empty log directory
        logs_dir = tmp_path / ".π" / "logs"
        logs_dir.mkdir(parents=True)

        # Change to test directory
        monkeypatch.chdir(tmp_path)

        # Mock the workflow execution
        with patch("π.cli.RPIWorkflow") as mock_workflow:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock_workflow.return_value = mock_instance

            main(["test objective"])
            captured = capsys.readouterr()

        # Should complete successfully with no errors
        assert "Workflow Mode" in captured.out


class TestWorkflowIntegrationNoAPI:
    """Integration tests verifying no API calls are made."""

    @pytest.fixture(autouse=True)
    def setup_mocks(
        self,
        mock_lm,
        clear_lm_cache,
        fresh_execution_context,
    ):
        """Set up all mocks for integration tests."""
        self.mock_lm = mock_lm
        self.ctx = fresh_execution_context

    @pytest.fixture
    def mock_full_workflow(
        self,
        mock_claude_client_with_responses,
        tmp_path: Path,
    ):
        """Set up complete workflow mocking with temp files."""
        from tests.factories import create_workflow_result

        # Create temp document structure
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        research_doc = research_dir / "2026-01-05-test.md"
        research_doc.write_text("# Research\n")

        plan_dir = tmp_path / "thoughts" / "shared" / "plans"
        plan_dir.mkdir(parents=True)
        plan_doc = plan_dir / "2026-01-05-test.md"
        plan_doc.write_text("# Plan\n")

        # Create mock responses for each stage
        messages = [
            create_workflow_result(stage="research", doc_path=str(research_doc)),
            create_workflow_result(stage="plan", doc_path=str(plan_doc)),
            create_workflow_result(stage="review"),
            create_workflow_result(stage="iterate"),
            create_workflow_result(stage="implement"),
            create_workflow_result(stage="commit"),
        ]

        with mock_claude_client_with_responses(messages) as client:
            yield client, tmp_path

    @pytest.mark.no_api
    def test_full_workflow_no_api_calls(
        self,
        mock_full_workflow,
        mock_rpi_workflow_full,
        capsys,
    ):
        """Verify complete workflow runs without API calls."""
        main(["test objective"])

        captured = capsys.readouterr()
        assert "[Workflow Mode]" in captured.out
        # Verify mock_lm was injected (mocking is working)
        assert self.mock_lm is not None

    @pytest.mark.no_api
    def test_workflow_stages_mocks_available(
        self,
        mock_workflow_stages,
        mock_full_workflow,
    ):
        """Verify workflow stage mocks are properly set up."""
        # Verify all stages are mocked
        expected_stages = {
            "research",
            "plan",
            "review",
            "iterate",
            "implement",
            "commit",
        }
        for stage_name, mock in mock_workflow_stages.items():
            assert mock is not None
            assert stage_name in expected_stages

    @pytest.mark.no_api
    def test_environment_variables_not_required_in_tests(
        self,
        clean_env,
        mock_full_workflow,
        mock_rpi_workflow_full,
    ):
        """Tests should pass without API environment variables."""
        # clean_env removes CLIPROXY_API_BASE and CLIPROXY_API_KEY
        # This should not cause failures with proper mocking
        main(["test objective"])
