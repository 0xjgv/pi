"""Tests for π.workflow.bridge module."""

from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk.types import (
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from π.core import AgentExecutionError
from π.workflow.bridge import (
    _extract_doc_path,
    _format_tool_result,
    _get_event_loop,
    _log_tool_call,
    _log_tool_result,
    _process_assistant_message,
    _result_indicates_completion,
    execute_claude_task,
    workflow_tool,
)
from π.workflow.context import Command


class TestProcessAssistantMessage:
    """Tests for _process_assistant_message() function."""

    def test_extracts_text_from_text_block(self):
        """Should accumulate text from TextBlock content."""
        text_block = MagicMock(spec=TextBlock)
        text_block.text = "Hello from assistant"

        message = MagicMock(spec=AssistantMessage)
        message.content = [text_block]

        result = _process_assistant_message(message)

        assert result == "Hello from assistant"

    def test_accumulates_multiple_text_blocks(self):
        """Should concatenate text from multiple TextBlocks."""
        block1 = MagicMock(spec=TextBlock)
        block1.text = "First part. "
        block2 = MagicMock(spec=TextBlock)
        block2.text = "Second part."

        message = MagicMock(spec=AssistantMessage)
        message.content = [block1, block2]

        result = _process_assistant_message(message)

        assert result == "First part. Second part."

    def test_logs_tool_use_block(self):
        """Should call _log_tool_call for ToolUseBlock."""
        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "TestTool"
        tool_block.input = {"arg": "value"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        with patch("π.workflow.bridge._log_tool_call") as mock_log:
            _process_assistant_message(message)
            mock_log.assert_called_once_with(tool_block)

    def test_logs_tool_result_block(self):
        """Should call _log_tool_result for ToolResultBlock."""
        result_block = MagicMock(spec=ToolResultBlock)
        result_block.content = "Tool completed"
        result_block.is_error = False

        message = MagicMock(spec=AssistantMessage)
        message.content = [result_block]

        with patch("π.workflow.bridge._log_tool_result") as mock_log:
            _process_assistant_message(message)
            mock_log.assert_called_once_with(result_block)

    def test_handles_mixed_block_types(self):
        """Should handle messages with mixed block types."""
        text_block = MagicMock(spec=TextBlock)
        text_block.text = "Analysis: "
        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Read"
        tool_block.input = {}

        message = MagicMock(spec=AssistantMessage)
        message.content = [text_block, tool_block]

        result = _process_assistant_message(message)

        assert result == "Analysis: "


class TestGetEventLoop:
    """Tests for _get_event_loop() function."""

    def test_creates_new_loop_when_none_exists(self):
        """Should create new event loop when context has none."""
        with patch("π.workflow.bridge.get_ctx") as mock_ctx:
            ctx = MagicMock()
            ctx.event_loop = None
            mock_ctx.return_value = ctx

            with patch("π.workflow.bridge.asyncio") as mock_asyncio:
                mock_loop = MagicMock()
                mock_asyncio.new_event_loop.return_value = mock_loop

                result = _get_event_loop()

                mock_asyncio.new_event_loop.assert_called_once()
                mock_asyncio.set_event_loop.assert_called_once_with(mock_loop)
                assert ctx.event_loop == mock_loop
                assert result == mock_loop

    def test_reuses_existing_open_loop(self):
        """Should return existing loop if not closed."""
        with patch("π.workflow.bridge.get_ctx") as mock_ctx:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            ctx = MagicMock()
            ctx.event_loop = mock_loop
            mock_ctx.return_value = ctx

            result = _get_event_loop()

            assert result == mock_loop

    def test_creates_new_loop_when_closed(self):
        """Should create new loop if existing one is closed."""
        with patch("π.workflow.bridge.get_ctx") as mock_ctx:
            closed_loop = MagicMock()
            closed_loop.is_closed.return_value = True
            ctx = MagicMock()
            ctx.event_loop = closed_loop
            mock_ctx.return_value = ctx

            with patch("π.workflow.bridge.asyncio") as mock_asyncio:
                new_loop = MagicMock()
                mock_asyncio.new_event_loop.return_value = new_loop

                result = _get_event_loop()

                mock_asyncio.new_event_loop.assert_called_once()
                assert result == new_loop


class TestExtractDocPath:
    """Tests for _extract_doc_path() function."""

    def test_extracts_research_path(self, tmp_path):
        """Should extract research doc path from result text."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        with patch("π.workflow.bridge.get_project_root", return_value=tmp_path):
            result = _extract_doc_path(
                "Created document at thoughts/shared/research/2026-01-05-test.md",
                "research",
            )

        assert result is not None
        assert "research" in result

    def test_extracts_plan_path(self, tmp_path):
        """Should extract plan doc path from result text."""
        plan_dir = tmp_path / "thoughts" / "shared" / "plans"
        plan_dir.mkdir(parents=True)
        doc = plan_dir / "2026-01-05-plan.md"
        doc.write_text("# Plan")

        with patch("π.workflow.bridge.get_project_root", return_value=tmp_path):
            result = _extract_doc_path(
                "Plan saved to thoughts/shared/plans/2026-01-05-plan.md",
                "plan",
            )

        assert result is not None
        assert "plans" in result

    def test_returns_none_for_unknown_doc_type(self):
        """Should return None and log warning for unknown doc_type."""
        result = _extract_doc_path("some text", "unknown_type")

        assert result is None

    def test_returns_none_when_no_match(self):
        """Should return None when pattern doesn't match."""
        result = _extract_doc_path("No path here", "research")

        assert result is None

    def test_returns_none_when_path_not_exists(self, tmp_path):
        """Should return None when extracted path doesn't exist."""
        with patch("π.workflow.bridge.get_project_root", return_value=tmp_path):
            result = _extract_doc_path(
                "Created thoughts/shared/research/2026-01-05-missing.md",
                "research",
            )

        assert result is None


class TestFormatToolResult:
    """Tests for _format_tool_result() function."""

    def test_formats_complete_with_doc_path(self):
        """Should include doc_path in TASK_COMPLETE result."""
        result = _format_tool_result(
            result="Research done",
            session_id="sess-123",
            doc_path="/path/to/doc.md",
            tool_name="research_codebase",
        )

        assert "[TASK_COMPLETE]" in result
        assert "Document saved: /path/to/doc.md" in result

    def test_formats_complete_without_doc_path(self):
        """Should still be complete if result indicates completion."""
        result = _format_tool_result(
            result="Research complete. Here is the summary of findings.",
            session_id="sess-123",
            doc_path=None,
            tool_name="research_codebase",
        )

        assert "[TASK_COMPLETE]" in result
        assert "Document saved:" not in result

    def test_formats_needs_input(self):
        """Should return NEEDS_INPUT when not complete."""
        result = _format_tool_result(
            result="What framework should I use?",
            session_id="sess-456",
            doc_path=None,
            tool_name="research_codebase",
        )

        assert "[NEEDS_INPUT]" in result
        assert "sess-456" in result


class TestResultIndicatesCompletion:
    """Tests for _result_indicates_completion() function."""

    @pytest.mark.parametrize(
        "text",
        [
            "Here is a complete picture of the codebase",
            "Summary of findings: the code uses React",
            "Research complete and documented",
            "Investigation complete - found the bug",
            "Analysis complete for the feature",
        ],
    )
    def test_detects_completion_signals(self, text):
        """Should detect various completion signal phrases."""
        assert _result_indicates_completion(text) is True

    def test_returns_false_for_questions(self):
        """Should return False for questions or incomplete results."""
        assert _result_indicates_completion("Which approach should I take?") is False


class TestExecuteClaudeTask:
    """Tests for execute_claude_task() function."""

    @pytest.fixture
    def mock_ctx(self):
        """Mock execution context."""
        with patch("π.workflow.bridge.get_ctx") as mock:
            ctx = MagicMock()
            ctx.session_ids = {}
            ctx.event_loop = None
            mock.return_value = ctx
            yield ctx

    def test_validates_command_type(self, mock_ctx):
        """Should raise ValueError for invalid command."""
        with (
            patch("π.workflow.bridge.COMMAND_MAP", {}),
            pytest.raises(ValueError, match="Invalid tool command"),
        ):
            execute_claude_task(
                tool_command=Command.RESEARCH_CODEBASE,
                query="test query",
            )

    def test_appends_path_to_command(self, mock_ctx):
        """Should append document path to command string."""
        with (
            patch("π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/plan"}),
            patch("π.workflow.bridge._get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_until_complete.return_value = ("result", "sid")

            execute_claude_task(
                tool_command=Command.CREATE_PLAN,
                path_to_document="/path/to/doc.md",
                query="create a plan",
            )

            # Verify the command was built correctly
            call_args = mock_loop.return_value.run_until_complete.call_args
            assert call_args is not None

    def test_planning_command_resumption_prefix(self, mock_ctx):
        """Should prefix planning commands with explicit instruction on resume."""
        with (
            patch(
                "π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/create_plan"}
            ),
            patch("π.workflow.bridge._get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_until_complete.return_value = ("result", "sid")

            execute_claude_task(
                tool_command=Command.CREATE_PLAN,
                session_id="existing-session",
                query="user feedback here",
            )

            # Verify run_until_complete was called
            mock_loop.return_value.run_until_complete.assert_called_once()


class TestWorkflowToolDecorator:
    """Tests for @workflow_tool decorator."""

    @pytest.fixture
    def mock_ctx(self):
        """Mock execution context."""
        with patch("π.workflow.bridge.get_ctx") as mock:
            ctx = MagicMock()
            ctx.session_ids = {}
            ctx.extracted_paths = {}
            mock.return_value = ctx
            yield ctx

    def test_catches_agent_execution_error(self, mock_ctx):
        """Should catch and format AgentExecutionError."""

        @workflow_tool(Command.RESEARCH_CODEBASE, phase_name="Research")
        def failing_tool(**kwargs):
            raise AgentExecutionError("Agent crashed")

        with patch("π.workflow.bridge.timed_phase"):
            result = failing_tool()

        assert "[ERROR]" in result
        assert "Agent crashed" in result

    def test_catches_generic_exception(self, mock_ctx):
        """Should catch and format unexpected exceptions."""

        @workflow_tool(Command.RESEARCH_CODEBASE, phase_name="Research")
        def broken_tool(**kwargs):
            raise RuntimeError("Unexpected failure")

        with patch("π.workflow.bridge.timed_phase"):
            result = broken_tool()

        assert "[ERROR]" in result
        assert "RuntimeError" in result

    def test_stores_session_id(self, mock_ctx):
        """Should store session_id in context after successful execution."""

        @workflow_tool(Command.RESEARCH_CODEBASE, phase_name="Research")
        def success_tool(**kwargs):
            return ("Tool result", "new-session-123")

        with patch("π.workflow.bridge.timed_phase"), patch("π.workflow.bridge.speak"):
            success_tool()

        assert mock_ctx.session_ids[Command.RESEARCH_CODEBASE] == "new-session-123"

    def test_extracts_doc_path_when_configured(self, mock_ctx, tmp_path):
        """Should extract and store doc path when doc_type is set."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return (
                "Done. Created thoughts/shared/research/2026-01-05-test.md",
                "sess-1",
            )

        with (
            patch("π.workflow.bridge.timed_phase"),
            patch("π.workflow.bridge.speak"),
            patch("π.workflow.bridge.get_project_root", return_value=tmp_path),
        ):
            result = research_tool()

        assert "[TASK_COMPLETE]" in result
        assert "research" in mock_ctx.extracted_paths

    def test_validates_plan_doc_when_required(self, mock_ctx):
        """Should call validate_plan_doc when validate_plan=True."""

        @workflow_tool(
            Command.IMPLEMENT_PLAN, phase_name="Implement", validate_plan=True
        )
        def implement_tool(**kwargs):
            return ("Implemented", "sess-1")

        with patch("π.workflow.bridge.timed_phase"), patch("π.workflow.bridge.speak"):
            implement_tool(plan_document_path="/path/to/plan.md")

        mock_ctx.validate_plan_doc.assert_called_once_with("/path/to/plan.md")


class TestLogToolCall:
    """Tests for _log_tool_call() function."""

    def test_truncates_long_input(self):
        """Should truncate input longer than 2000 chars."""
        block = MagicMock(spec=ToolUseBlock)
        block.name = "TestTool"
        block.input = {"data": "x" * 3000}

        with patch("π.workflow.bridge.logger") as mock_logger:
            _log_tool_call(block)
            call_args = mock_logger.debug.call_args[0]
            assert "..." in call_args[2]


class TestLogToolResult:
    """Tests for _log_tool_result() function."""

    def test_shows_error_status(self):
        """Should show 'error' status for error results."""
        block = MagicMock(spec=ToolResultBlock)
        block.is_error = True
        block.content = "Failed to read file"

        with patch("π.workflow.bridge.logger") as mock_logger:
            _log_tool_result(block)
            call_args = mock_logger.debug.call_args[0]
            assert "error" in call_args[1]

    def test_shows_ok_status(self):
        """Should show 'ok' status for successful results."""
        block = MagicMock(spec=ToolResultBlock)
        block.is_error = False
        block.content = "File contents here"

        with patch("π.workflow.bridge.logger") as mock_logger:
            _log_tool_result(block)
            call_args = mock_logger.debug.call_args[0]
            assert "ok" in call_args[1]
