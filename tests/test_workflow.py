"""Tests for π.workflow module."""

import asyncio
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk.types import ResultMessage

from π.errors import AgentExecutionError
from π.session import Command
from π.workflow import (
    _get_agent_options,
    _get_event_loop,
    _get_session,
    _log_result_metrics,
    _log_tool_call,
    _log_tool_result,
    clarify_goal,
    create_plan,
    implement_plan,
    research_codebase,
    timed_phase,
)


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
        with patch("π.workflow.time") as mock_time:
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
        block.name = "TestTool"
        block.input = {"key": "value"}

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_call(block)

        assert "TestTool" in caplog.text
        assert "key" in caplog.text

    def test_log_tool_call_truncates_long_input(self, caplog: pytest.LogCaptureFixture):
        """Should truncate inputs longer than 100 chars."""
        import logging

        from claude_agent_sdk.types import ToolUseBlock

        block = MagicMock(spec=ToolUseBlock)
        block.name = "TestTool"
        block.input = {"data": "x" * 200}

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_call(block)

        assert "..." in caplog.text

    def test_log_tool_result_shows_status(self, caplog: pytest.LogCaptureFixture):
        """Should log 'ok' or 'error' status."""
        import logging

        from claude_agent_sdk.types import ToolResultBlock

        success_block = MagicMock(spec=ToolResultBlock)
        success_block.is_error = False
        success_block.content = "Success"

        error_block = MagicMock(spec=ToolResultBlock)
        error_block.is_error = True
        error_block.content = "Failed"

        with caplog.at_level(logging.DEBUG, logger="π.workflow"):
            _log_tool_result(success_block)
            assert "[ok]" in caplog.text

            caplog.clear()
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

    def test_get_event_loop_creates_new_loop(self):
        """Should create a new event loop if none exists."""
        loop = _get_event_loop()

        assert isinstance(loop, asyncio.AbstractEventLoop)
        assert not loop.is_closed()

    def test_get_event_loop_reuses_existing(self):
        """Should reuse existing loop if not closed."""
        loop1 = _get_event_loop()
        loop2 = _get_event_loop()

        assert loop1 is loop2

    def test_get_session_creates_new_session(self):
        """Should create new WorkflowSession if none exists."""
        from π.session import WorkflowSession

        session = _get_session()

        assert isinstance(session, WorkflowSession)

    def test_get_agent_options_returns_options(self):
        """Should return ClaudeAgentOptions."""
        from claude_agent_sdk import ClaudeAgentOptions

        options = _get_agent_options()

        assert isinstance(options, ClaudeAgentOptions)


class TestWorkflowFunctions:
    """Tests for workflow functions (research, plan, implement, clarify)."""

    @pytest.fixture
    def mock_execute_task(self) -> Generator[MagicMock, None, None]:
        """Mock _execute_claude_task."""
        with patch("π.workflow._execute_claude_task") as mock:
            mock.return_value = ("Result text", "session-123")
            yield mock

    def test_research_codebase_returns_result(
        self,
        mock_execute_task: MagicMock,  # noqa: ARG002
    ):
        """Should return result with session ID."""
        result = research_codebase(query="test query")

        assert "Result:" in result
        assert "session-123" in result

    def test_research_codebase_passes_query(self, mock_execute_task: MagicMock):
        """Should pass query to execute task."""
        research_codebase(query="find all tests")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["query"] == "find all tests"
        assert call_kwargs["tool_command"] == Command.RESEARCH_CODEBASE

    def test_clarify_goal_returns_result(
        self,
        mock_execute_task: MagicMock,  # noqa: ARG002
    ):
        """Should return clarification result."""
        result = clarify_goal(query="what do you mean?")

        assert "Result:" in result
        assert "Clarification Session ID" in result

    def test_create_plan_requires_research_path(self, mock_execute_task: MagicMock):
        """Should pass research document path."""
        create_plan(
            query="create plan",
            research_document_path=Path("/path/to/research.md"),
        )

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["path_to_document"] == Path("/path/to/research.md")

    def test_implement_plan_validates_plan_doc(self):
        """Should validate plan document is not research doc."""
        from π.session import WorkflowSession
        from π.workflow import _session_var

        # Set up a session with research doc
        session = WorkflowSession()
        session.set_doc_path(Command.CREATE_PLAN, "/research.md")
        _session_var.set(session)

        # Should raise when plan path matches research doc
        with pytest.raises(ValueError) as exc_info:
            implement_plan(
                query="implement",
                plan_document_path=Path("/research.md"),
            )

        assert "implement_plan requires the PLAN document" in str(exc_info.value)

    def test_workflow_handles_agent_error(self, mock_execute_task: MagicMock):
        """Should return error message on AgentExecutionError."""
        mock_execute_task.side_effect = AgentExecutionError("Agent failed")

        result = research_codebase(query="test")

        assert "[ERROR]" in result
        assert "Agent failed" in result

    def test_auto_resumes_existing_session(self, mock_execute_task: MagicMock):
        """Should automatically resume when session exists."""
        from π.session import WorkflowSession
        from π.workflow import _session_var

        session = WorkflowSession()
        session.set_session_id(Command.RESEARCH_CODEBASE, "auto-resume-session")
        _session_var.set(session)

        research_codebase(query="continue work")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["session_id"] == "auto-resume-session"

    def test_starts_new_session_when_none_exists(self, mock_execute_task: MagicMock):
        """Should start new session when no prior session exists."""
        from π.session import WorkflowSession
        from π.workflow import _session_var

        session = WorkflowSession()  # Fresh session, no IDs
        _session_var.set(session)

        research_codebase(query="new research")

        call_kwargs = mock_execute_task.call_args.kwargs
        assert call_kwargs["session_id"] is None

    def test_stores_session_for_future_resumption(self, mock_execute_task: MagicMock):
        """Should store session ID for future auto-resumption."""
        from π.session import WorkflowSession
        from π.workflow import _session_var

        mock_execute_task.return_value = ("Result", "new-session-xyz")
        session = WorkflowSession()
        _session_var.set(session)

        research_codebase(query="first call")

        # Session should now be stored
        assert session.get_session_id(Command.RESEARCH_CODEBASE) == "new-session-xyz"
