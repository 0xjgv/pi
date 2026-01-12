"""Tests for π.workflow module."""

import asyncio
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk.types import ResultMessage

from π.core import AgentExecutionError
from π.workflow import (
    Command,
    create_plan,
    iterate_plan,
    research_codebase,
)
from π.workflow.bridge import (
    SessionWriteTracker,
    _get_agent_options,
    _log_result_metrics,
    _log_tool_call,
    _log_tool_result,
    get_ctx,
    timed_phase,
)
from π.workflow.context import get_event_loop

# Module-level tracker for fixture use (ensures SessionWriteTracker import is used)
_MOCK_TRACKER = SessionWriteTracker()


class TestTimedPhase:
    """Tests for timed_phase context manager."""

    def test_displays_phase_name(self, capsys: pytest.CaptureFixture):
        """Should display phase name on completion."""
        with timed_phase("Test Phase"):
            pass

        captured = capsys.readouterr()
        assert "Test Phase" in captured.out

    def test_shows_elapsed_time(self, capsys: pytest.CaptureFixture):
        """Should show elapsed time in output."""
        import time

        with timed_phase("Timed Test"):
            time.sleep(0.1)

        captured = capsys.readouterr()
        # Should show time (either seconds or minutes format)
        assert "s" in captured.out or "m" in captured.out

    def test_formats_minutes_correctly(self, capsys: pytest.CaptureFixture):
        """Should format times over 60s as minutes."""
        # Mock time.monotonic to simulate long duration
        with patch("π.workflow.bridge.time") as mock_time:
            mock_time.monotonic.side_effect = [0, 125]  # 2m 5s

            with timed_phase("Long Task"):
                pass

        captured = capsys.readouterr()
        assert "2m" in captured.out


class TestLogHelpers:
    """Tests for logging helper functions."""

    def test_log_tool_call_logs_name_and_input(self, caplog: pytest.LogCaptureFixture):
        """Should log tool name and truncated input."""
        import logging

        from claude_agent_sdk.types import ToolUseBlock

        block = MagicMock(spec=ToolUseBlock)
        block.id = "tool-123"
        block.name = "TestTool"
        block.input = {"key": "value"}

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_call(block)

        assert "TestTool" in caplog.text
        assert "key" in caplog.text

    def test_log_tool_call_truncates_long_input(self, caplog: pytest.LogCaptureFixture):
        """Should truncate inputs longer than 2000 chars."""
        import logging

        from claude_agent_sdk.types import ToolUseBlock

        block = MagicMock(spec=ToolUseBlock)
        block.id = "tool-124"
        block.name = "TestTool"
        block.input = {"data": "x" * 2100}  # 2100 chars exceeds 2000 limit

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_call(block)

        assert "..." in caplog.text

    def test_log_tool_result_shows_status(self, caplog: pytest.LogCaptureFixture):
        """Should log 'ok' or 'error' status."""
        import logging

        from claude_agent_sdk.types import ToolResultBlock

        success_block = MagicMock(spec=ToolResultBlock)
        success_block.tool_use_id = "tool-123"
        success_block.is_error = False
        success_block.content = "Success"

        error_block = MagicMock(spec=ToolResultBlock)
        error_block.tool_use_id = "tool-124"
        error_block.is_error = True
        error_block.content = "Failed"

        # Non-important tool results logged at DEBUG, errors at INFO
        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_result(success_block)
            assert "[ok]" in caplog.text

            caplog.clear()

        with caplog.at_level(logging.INFO, logger="π.workflow"):
            _log_tool_result(error_block)
            assert "[error]" in caplog.text

    def test_log_result_metrics_logs_all_fields(self, caplog: pytest.LogCaptureFixture):
        """Should log turns, duration, cost, and tokens."""
        import logging

        message = MagicMock(spec=ResultMessage)
        message.num_turns = 5
        message.duration_ms = 2000
        message.duration_api_ms = 1500
        message.total_cost_usd = 0.05
        message.usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50,
        }

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_result_metrics(message)

        assert "turns=5" in caplog.text
        assert "$0.05" in caplog.text or "0.0500" in caplog.text


class TestContextVarHelpers:
    """Tests for context variable helpers."""

    def test_get_event_loop_creates_new_loop(self, fresh_execution_context):
        """Should create a new event loop if none exists."""
        loop = get_event_loop()

        assert isinstance(loop, asyncio.AbstractEventLoop)
        assert not loop.is_closed()

        # Cleanup to avoid ResourceWarning
        loop.close()

    def test_get_event_loop_reuses_existing(self, fresh_execution_context):
        """Should reuse existing loop if not closed."""
        loop1 = get_event_loop()
        loop2 = get_event_loop()

        assert loop1 is loop2

        # Cleanup to avoid ResourceWarning
        loop1.close()

    def test_get_ctx_creates_new_context(self):
        """Should create new ExecutionContext if none exists."""
        from π.workflow import ExecutionContext

        ctx = get_ctx()

        assert isinstance(ctx, ExecutionContext)

    def test_get_agent_options_returns_options(self):
        """Should return ClaudeAgentOptions."""
        from claude_agent_sdk import ClaudeAgentOptions

        options = _get_agent_options()

        assert isinstance(options, ClaudeAgentOptions)


class TestWorkflowFunctions:
    """Tests for workflow functions (research, plan, implement, clarify)."""

    @pytest.fixture
    def mock_execute_task(self) -> Generator[MagicMock]:
        """Mock execute_claude_task.

        Patches at tools.py where the function is used, not bridge.py
        where it's defined.
        """
        with patch("π.workflow.tools.execute_claude_task") as mock:
            mock.return_value = ("Result text", "session-123", _MOCK_TRACKER)
            yield mock

    def test_research_codebase_returns_result(
        self,
        mock_execute_task: MagicMock,
    ):
        """Should return result with session ID."""
        result = research_codebase(query="test query")

        # Result should contain session context in XML format
        assert "<session_id>session-123</session_id>" in result

    def test_research_codebase_passes_query(self, mock_execute_task: MagicMock):
        """Should pass query to execute task."""
        research_codebase(query="find all tests")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["query"] == "find all tests"
        assert call_kwargs["tool_command"] == Command.RESEARCH_CODEBASE

    def test_create_plan_requires_research_path(self, mock_execute_task: MagicMock):
        """Should pass research document paths."""
        create_plan(
            query="create plan",
            research_document_paths=[Path("/path/to/research.md")],
        )

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["path_to_documents"] == [Path("/path/to/research.md")]

    def test_iterate_plan_validates_plan_doc(self, mock_execute_task: MagicMock):
        """Should validate plan document via PlanDocPath.

        Note: The actual validation logic is tested in test_bridge.py. This test
        verifies the tool integration uses get_or_validate_plan_path which
        validates via PlanDocPath (directory, extension, existence, date prefix).
        """
        from π.workflow.bridge import _ctx
        from π.workflow.context import ExecutionContext

        ctx = ExecutionContext()
        _ctx.set(ctx)

        # Should raise when plan path is not in correct directory
        with pytest.raises(ValueError) as exc_info:
            iterate_plan(
                review_feedback="implement",
                plan_document_path="/invalid/path.md",
            )

        # PlanDocPath validates directory first
        assert "must be in thoughts/shared/plans" in str(exc_info.value)

    def test_workflow_handles_agent_error(self, mock_execute_task: MagicMock):
        """Should return error message on AgentExecutionError."""
        mock_execute_task.side_effect = AgentExecutionError("Agent failed")

        result = research_codebase(query="test")

        assert "[ERROR]" in result
        assert "Agent failed" in result

    def test_auto_resumes_existing_session(self, mock_execute_task: MagicMock):
        """Should automatically resume when session exists."""
        from π.workflow.bridge import _ctx
        from π.workflow.context import ExecutionContext

        ctx = ExecutionContext()
        ctx.session_ids[Command.RESEARCH_CODEBASE] = "auto-resume-session"
        _ctx.set(ctx)

        research_codebase(query="continue work")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["session_id"] == "auto-resume-session"

    def test_starts_new_session_when_none_exists(self, mock_execute_task: MagicMock):
        """Should start new session when no prior session exists."""
        from π.workflow.bridge import _ctx
        from π.workflow.context import ExecutionContext

        ctx = ExecutionContext()  # Fresh context, no IDs
        _ctx.set(ctx)

        research_codebase(query="new research")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["session_id"] is None

    def test_stores_session_for_future_resumption(self, mock_execute_task: MagicMock):
        """Should store session ID for future auto-resumption."""
        from π.workflow.bridge import _ctx
        from π.workflow.context import ExecutionContext

        mock_execute_task.return_value = ("Result", "new-session-xyz", _MOCK_TRACKER)
        ctx = ExecutionContext()
        _ctx.set(ctx)

        research_codebase(query="first call")

        # Session should now be stored
        assert ctx.session_ids.get(Command.RESEARCH_CODEBASE) == "new-session-xyz"


class TestCommandEnumAndMapping:
    """Tests for Command enum and build_command_map."""

    def test_write_claude_md_command_exists(self):
        """WRITE_CLAUDE_MD is a valid Command enum member."""
        assert hasattr(Command, "WRITE_CLAUDE_MD")
        assert Command.WRITE_CLAUDE_MD == "write_claude_md"

    def test_build_command_map_includes_non_numbered(self, tmp_path: Path):
        """build_command_map() includes non-numbered commands."""
        from π.workflow.context import build_command_map

        # Create test command file
        (tmp_path / "write-claude-md.md").write_text("# Test")

        cmd_map = build_command_map(command_dir=tmp_path)

        assert Command.WRITE_CLAUDE_MD in cmd_map
        assert cmd_map[Command.WRITE_CLAUDE_MD] == "/write-claude-md"

    def test_build_command_map_preserves_numbered(self, tmp_path: Path):
        """build_command_map() still discovers numbered commands."""
        from π.workflow.context import build_command_map

        # Create numbered command file
        (tmp_path / "1_research_codebase.md").write_text("# Test")

        cmd_map = build_command_map(command_dir=tmp_path)

        assert Command.RESEARCH_CODEBASE in cmd_map
        assert cmd_map[Command.RESEARCH_CODEBASE] == "/1_research_codebase"
