"""Tests for π.workflow.bridge module."""

from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_returns_session_context_without_doc_path(self):
        """Should return session context when no doc_path, letting DSPy decide."""
        result = _format_tool_result(
            result="Research findings about the codebase architecture.",
            session_id="sess-123",
            doc_path=None,
            tool_name="research_codebase",
        )

        # No completion marker - DSPy decides from context
        assert "[TASK_COMPLETE]" not in result
        assert "Session: sess-123" in result
        assert "Tool: research_codebase" in result
        assert "Continue with follow-up if needed" in result

    def test_includes_result_in_output(self):
        """Should include original result text in formatted output."""
        result = _format_tool_result(
            result="The codebase uses React with TypeScript.",
            session_id="sess-456",
            doc_path=None,
            tool_name="research_codebase",
        )

        assert "The codebase uses React with TypeScript." in result


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
        mock_session = AsyncMock(return_value=("result", "sid"))
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda coro: coro.close() or (
            "result",
            "sid",
        )
        with (
            patch("π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/plan"}),
            patch("π.workflow.bridge._run_claude_session", mock_session),
            patch("π.workflow.bridge._get_event_loop", return_value=mock_loop),
        ):
            execute_claude_task(
                tool_command=Command.CREATE_PLAN,
                path_to_documents=["/path/to/doc.md"],
                query="create a plan",
            )

            # Verify the command was built correctly with path appended
            mock_session.assert_called_once()
            call_args = mock_session.call_args[0]
            assert "/path/to/doc.md" in call_args[0]

    def test_planning_command_resumption_prefix(self, mock_ctx):
        """Should prefix planning commands with explicit instruction on resume."""
        mock_session = AsyncMock(return_value=("result", "sid"))
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda coro: coro.close() or (
            "result",
            "sid",
        )
        with (
            patch(
                "π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/create_plan"}
            ),
            patch("π.workflow.bridge._run_claude_session", mock_session),
            patch("π.workflow.bridge._get_event_loop", return_value=mock_loop),
        ):
            execute_claude_task(
                tool_command=Command.CREATE_PLAN,
                session_id="existing-session",
                query="user feedback here",
            )

            # Verify _run_claude_session was called with session_id
            mock_session.assert_called_once()
            call_args = mock_session.call_args[0]
            assert call_args[1] == "existing-session"


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
        paths = mock_ctx.extracted_paths["research"]
        assert any("2026-01-05-test.md" in p for p in paths)

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


class TestSessionClearingOnDocExtraction:
    """Tests for session clearing when document is extracted."""

    @pytest.fixture
    def mock_ctx(self):
        """Mock execution context with session_ids and extracted_results."""
        with patch("π.workflow.bridge.get_ctx") as mock:
            ctx = MagicMock()
            ctx.session_ids = {Command.RESEARCH_CODEBASE: "existing-session"}
            ctx.extracted_paths = {}
            ctx.extracted_results = {}
            mock.return_value = ctx
            yield ctx

    def test_clears_session_when_doc_extracted(self, mock_ctx, tmp_path):
        """Should clear session_id when document is extracted."""
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
                "new-session",
            )

        with (
            patch("π.workflow.bridge.timed_phase"),
            patch("π.workflow.bridge.speak"),
            patch("π.workflow.bridge.get_project_root", return_value=tmp_path),
        ):
            research_tool()

        # Session should be cleared after doc extraction
        assert Command.RESEARCH_CODEBASE not in mock_ctx.session_ids

    def test_preserves_session_when_no_doc(self, mock_ctx):
        """Should preserve session_id when no document is extracted."""

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return ("What framework should I use?", "new-session")

        with (
            patch("π.workflow.bridge.timed_phase"),
            patch("π.workflow.bridge.speak"),
        ):
            research_tool()

        # Session should still be stored (for clarification flow)
        assert mock_ctx.session_ids[Command.RESEARCH_CODEBASE] == "new-session"

    def test_stores_extracted_results(self, mock_ctx, tmp_path):
        """Should store extracted results when doc is extracted."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return (
                "Research complete. "
                "Created thoughts/shared/research/2026-01-05-test.md",
                "sess-1",
            )

        with (
            patch("π.workflow.bridge.timed_phase"),
            patch("π.workflow.bridge.speak"),
            patch("π.workflow.bridge.get_project_root", return_value=tmp_path),
        ):
            research_tool()

        # Should have one result stored
        assert len(mock_ctx.extracted_results) == 1
        doc_path = next(iter(mock_ctx.extracted_results.keys()))
        assert "2026-01-05-test.md" in doc_path
        assert "Research complete" in mock_ctx.extracted_results[doc_path]
