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
    SessionWriteTracker,
    _extract_doc_path,
    _format_tool_result,
    _log_tool_call,
    _log_tool_result,
    _process_assistant_message,
    execute_claude_task,
    workflow_tool,
)
from π.workflow.context import Command, get_event_loop


class TestSessionWriteTracker:
    """Tests for SessionWriteTracker."""

    def test_confirmed_write_stored(self):
        """Confirmed writes stored by doc_type."""
        tracker = SessionWriteTracker()
        tracker.on_tool_use("tool_1", "thoughts/shared/research/doc.md")
        tracker.on_tool_result("tool_1", is_error=False)

        assert tracker.writes["research"] == ["thoughts/shared/research/doc.md"]

    def test_failed_write_excluded(self):
        """Failed writes not stored."""
        tracker = SessionWriteTracker()
        tracker.on_tool_use("tool_1", "thoughts/shared/research/doc.md")
        tracker.on_tool_result("tool_1", is_error=True)

        assert "research" not in tracker.writes

    def test_multiple_writes_all_tracked(self):
        """Multiple writes to same doc_type: all tracked in order."""
        tracker = SessionWriteTracker()
        tracker.on_tool_use("t1", "thoughts/shared/research/first.md")
        tracker.on_tool_result("t1", is_error=False)
        tracker.on_tool_use("t2", "thoughts/shared/research/second.md")
        tracker.on_tool_result("t2", is_error=False)

        assert tracker.writes["research"] == [
            "thoughts/shared/research/first.md",
            "thoughts/shared/research/second.md",
        ]

    def test_infer_doc_type_research(self):
        """Doc type inference for research path."""
        assert (
            SessionWriteTracker._infer_doc_type("thoughts/shared/research/x.md")
            == "research"
        )

    def test_infer_doc_type_plan(self):
        """Doc type inference for plan path."""
        assert (
            SessionWriteTracker._infer_doc_type("thoughts/shared/plans/x.md") == "plan"
        )

    def test_infer_doc_type_unknown(self):
        """Doc type inference returns None for unknown paths."""
        assert SessionWriteTracker._infer_doc_type("src/main.py") is None

    def test_get_paths_returns_existing_in_order(self, tmp_path):
        """get_paths returns all existing files in write order."""
        with patch("π.workflow.bridge.get_project_root", return_value=tmp_path):
            (tmp_path / "thoughts/shared/research").mkdir(parents=True)
            (tmp_path / "thoughts/shared/research/a.md").write_text("a")
            (tmp_path / "thoughts/shared/research/b.md").write_text("b")

            tracker = SessionWriteTracker()
            tracker.writes["research"] = [
                "thoughts/shared/research/a.md",
                "thoughts/shared/research/missing.md",  # doesn't exist - filtered out
                "thoughts/shared/research/b.md",
            ]

            paths = tracker.get_paths("research")
            assert len(paths) == 2
            assert paths[0].endswith("a.md")
            assert paths[1].endswith("b.md")  # Last = most recent

    def test_pending_cleared_after_result(self):
        """Pending write should be cleared after tool result."""
        tracker = SessionWriteTracker()
        tracker.on_tool_use("tool_1", "thoughts/shared/research/doc.md")
        assert "tool_1" in tracker._pending

        tracker.on_tool_result("tool_1", is_error=False)
        assert "tool_1" not in tracker._pending

    def test_unknown_tool_result_ignored(self):
        """Tool result for unknown tool_use_id should be ignored."""
        tracker = SessionWriteTracker()
        # No on_tool_use called, so this should not raise
        tracker.on_tool_result("unknown_id", is_error=False)
        assert tracker.writes == {}


class TestDocPathExtractionWithTracker:
    """Tests for _extract_doc_path with tracker."""

    def test_returns_tracked_path(self, tmp_path):
        """Returns most recent tracked path for doc_type."""
        with patch("π.workflow.bridge.get_project_root", return_value=tmp_path):
            (tmp_path / "thoughts/shared/research").mkdir(parents=True)
            (tmp_path / "thoughts/shared/research/new.md").write_text("new")

            tracker = SessionWriteTracker()
            tracker.writes["research"] = ["thoughts/shared/research/new.md"]

            extracted = _extract_doc_path("research", tracker)

            assert extracted == str(tmp_path / "thoughts/shared/research/new.md")

    def test_returns_none_when_no_tracker(self):
        """Returns None when tracker is None."""
        extracted = _extract_doc_path("research", tracker=None)
        assert extracted is None

    def test_returns_none_when_tracker_empty(self):
        """Returns None when tracker has no writes for doc_type."""
        tracker = SessionWriteTracker()  # Empty tracker
        extracted = _extract_doc_path("research", tracker)
        assert extracted is None


class TestProcessAssistantMessageWithTracker:
    """Tests for _process_assistant_message with tracker integration."""

    def test_tracks_write_tool_use(self):
        """Should track Write tool file_path in tracker."""
        tracker = SessionWriteTracker()

        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Write"
        tool_block.id = "tool_123"
        tool_block.input = {"file_path": "thoughts/shared/research/doc.md"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        _process_assistant_message(message, tracker)

        assert "tool_123" in tracker._pending
        assert tracker._pending["tool_123"] == (
            "research",
            "thoughts/shared/research/doc.md",
        )

    def test_tracks_edit_tool_use(self):
        """Should track Edit tool file_path in tracker."""
        tracker = SessionWriteTracker()

        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Edit"
        tool_block.id = "tool_456"
        tool_block.input = {"file_path": "thoughts/shared/plans/plan.md"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        _process_assistant_message(message, tracker)

        assert "tool_456" in tracker._pending

    def test_confirms_write_on_success_result(self):
        """Should confirm write when tool result is success."""
        tracker = SessionWriteTracker()
        tracker._pending["tool_123"] = ("research", "thoughts/shared/research/doc.md")

        result_block = MagicMock(spec=ToolResultBlock)
        result_block.tool_use_id = "tool_123"
        result_block.is_error = False

        message = MagicMock(spec=AssistantMessage)
        message.content = [result_block]

        _process_assistant_message(message, tracker)

        assert tracker.writes["research"] == ["thoughts/shared/research/doc.md"]
        assert "tool_123" not in tracker._pending

    def test_rejects_write_on_error_result(self):
        """Should reject write when tool result is error."""
        tracker = SessionWriteTracker()
        tracker._pending["tool_123"] = ("research", "thoughts/shared/research/doc.md")

        result_block = MagicMock(spec=ToolResultBlock)
        result_block.tool_use_id = "tool_123"
        result_block.is_error = True

        message = MagicMock(spec=AssistantMessage)
        message.content = [result_block]

        _process_assistant_message(message, tracker)

        assert "research" not in tracker.writes
        assert "tool_123" not in tracker._pending

    def test_ignores_non_write_tools(self):
        """Should not track Read/Grep/Glob tools."""
        tracker = SessionWriteTracker()

        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Read"
        tool_block.id = "tool_789"
        tool_block.input = {"file_path": "thoughts/shared/research/doc.md"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        _process_assistant_message(message, tracker)

        assert tracker._pending == {}

    def test_none_tracker_does_not_crash(self):
        """Should work without tracker (backwards compatible)."""
        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Write"
        tool_block.id = "tool_123"
        tool_block.input = {"file_path": "test.md"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        # Should not raise
        result = _process_assistant_message(message, tracker=None)
        assert result == ""


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
        result_block.tool_use_id = "tool-123"
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
        tool_block.id = "tool-123"
        tool_block.name = "Read"
        tool_block.input = {}

        message = MagicMock(spec=AssistantMessage)
        message.content = [text_block, tool_block]

        result = _process_assistant_message(message)

        assert result == "Analysis: "


class TestGetEventLoop:
    """Tests for get_event_loop() function."""

    def test_creates_new_loop_when_none_exists(self):
        """Should create new event loop when context has none."""
        with patch("π.workflow.context.get_ctx") as mock_ctx:
            ctx = MagicMock()
            ctx.event_loop = None
            mock_ctx.return_value = ctx

            with patch("π.workflow.context.asyncio") as mock_asyncio:
                mock_loop = MagicMock()
                mock_asyncio.new_event_loop.return_value = mock_loop

                result = get_event_loop()

                mock_asyncio.new_event_loop.assert_called_once()
                mock_asyncio.set_event_loop.assert_called_once_with(mock_loop)
                assert ctx.event_loop == mock_loop
                assert result == mock_loop

    def test_reuses_existing_open_loop(self):
        """Should return existing loop if not closed."""
        with patch("π.workflow.context.get_ctx") as mock_ctx:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            ctx = MagicMock()
            ctx.event_loop = mock_loop
            mock_ctx.return_value = ctx

            result = get_event_loop()

            assert result == mock_loop

    def test_creates_new_loop_when_closed(self):
        """Should create new loop if existing one is closed."""
        with patch("π.workflow.context.get_ctx") as mock_ctx:
            closed_loop = MagicMock()
            closed_loop.is_closed.return_value = True
            ctx = MagicMock()
            ctx.event_loop = closed_loop
            mock_ctx.return_value = ctx

            with patch("π.workflow.context.asyncio") as mock_asyncio:
                new_loop = MagicMock()
                mock_asyncio.new_event_loop.return_value = new_loop

                result = get_event_loop()

                mock_asyncio.new_event_loop.assert_called_once()
                assert result == new_loop


class TestFormatToolResult:
    """Tests for _format_tool_result() function."""

    def test_formats_complete_with_doc_path(self):
        """Should include doc_path in structured result."""
        result = _format_tool_result(
            result="Research done",
            session_id="sess-123",
            doc_path="/path/to/doc.md",
            tool_name="research_codebase",
        )

        assert "<session_id>sess-123</session_id>" in result
        assert "<tool_name>research_codebase</tool_name>" in result
        assert "<doc_path>/path/to/doc.md</doc_path>" in result

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
        assert "<session_id>sess-123</session_id>" in result
        assert "<tool_name>research_codebase</tool_name>" in result
        assert "<result>Research findings" in result

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
        mock_tracker = SessionWriteTracker()
        mock_session = AsyncMock(return_value=("result", "sid", mock_tracker))
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda coro: (
            coro.close()
            or (
                "result",
                "sid",
                mock_tracker,
            )
        )
        with (
            patch("π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/plan"}),
            patch("π.workflow.bridge._run_claude_session", mock_session),
            patch("π.workflow.bridge.get_event_loop", return_value=mock_loop),
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
        mock_tracker = SessionWriteTracker()
        mock_session = AsyncMock(return_value=("result", "sid", mock_tracker))
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda coro: (
            coro.close()
            or (
                "result",
                "sid",
                mock_tracker,
            )
        )
        with (
            patch(
                "π.workflow.bridge.COMMAND_MAP", {Command.CREATE_PLAN: "/create_plan"}
            ),
            patch("π.workflow.bridge._run_claude_session", mock_session),
            patch("π.workflow.bridge.get_event_loop", return_value=mock_loop),
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
            return ("Tool result", "new-session-123", SessionWriteTracker())

        with patch("π.workflow.bridge.timed_phase"), patch("π.workflow.bridge.speak"):
            success_tool()

        assert mock_ctx.session_ids[Command.RESEARCH_CODEBASE] == "new-session-123"

    def test_extracts_doc_path_when_configured(self, mock_ctx, tmp_path):
        """Should extract and store doc path when doc_type is set."""
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        # Create tracker with tracked write
        tracker = SessionWriteTracker()
        tracker.writes["research"] = ["thoughts/shared/research/2026-01-05-test.md"]

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return (
                "Done.",
                "sess-1",
                tracker,
            )

        with (
            patch("π.workflow.bridge.timed_phase"),
            patch("π.workflow.bridge.speak"),
            patch("π.workflow.bridge.get_project_root", return_value=tmp_path),
        ):
            result = research_tool()

        assert "<doc_path>" in result
        assert "2026-01-05-test.md" in result
        assert "research" in mock_ctx.extracted_paths
        paths = mock_ctx.extracted_paths["research"]
        assert any("2026-01-05-test.md" in p for p in paths)

    def test_validates_and_injects_plan_path(self, mock_ctx):
        """Should call get_or_validate_plan_path and inject result into kwargs."""
        mock_ctx.get_or_validate_plan_path.return_value = "/validated/plan.md"
        captured_kwargs = {}

        @workflow_tool(
            Command.IMPLEMENT_PLAN, phase_name="Implement", validate_plan=True
        )
        def implement_tool(**kwargs):
            captured_kwargs.update(kwargs)
            return ("Implemented", "sess-1", SessionWriteTracker())

        with patch("π.workflow.bridge.timed_phase"), patch("π.workflow.bridge.speak"):
            implement_tool(plan_document_path="/path/to/plan.md")

        mock_ctx.get_or_validate_plan_path.assert_called_once_with("/path/to/plan.md")
        assert captured_kwargs["plan_document_path"] == "/validated/plan.md"

    def test_auto_injects_plan_path_when_not_provided(self, mock_ctx):
        """Should auto-inject plan path from context when not provided."""
        mock_ctx.get_or_validate_plan_path.return_value = "/auto/selected/plan.md"
        captured_kwargs = {}

        @workflow_tool(
            Command.IMPLEMENT_PLAN, phase_name="Implement", validate_plan=True
        )
        def implement_tool(**kwargs):
            captured_kwargs.update(kwargs)
            return ("Implemented", "sess-1", SessionWriteTracker())

        with patch("π.workflow.bridge.timed_phase"), patch("π.workflow.bridge.speak"):
            implement_tool(query="test")  # No plan_document_path

        mock_ctx.get_or_validate_plan_path.assert_called_once_with(None)
        assert captured_kwargs["plan_document_path"] == "/auto/selected/plan.md"


class TestLogToolCall:
    """Tests for _log_tool_call() function."""

    def test_truncates_long_input(self):
        """Should truncate input longer than 2000 chars."""
        block = MagicMock(spec=ToolUseBlock)
        block.id = "tool-123"
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
        block.tool_use_id = "tool-123"
        block.is_error = True
        block.content = "Failed to read file"

        with patch("π.workflow.bridge.logger") as mock_logger:
            _log_tool_result(block)
            # Errors are logged at INFO level now
            call_args = mock_logger.info.call_args[0]
            assert "error" in call_args[1]

    def test_shows_ok_status(self):
        """Should show 'ok' status for successful results."""
        block = MagicMock(spec=ToolResultBlock)
        block.tool_use_id = "tool-123"
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

        # Create tracker with tracked write
        tracker = SessionWriteTracker()
        tracker.writes["research"] = ["thoughts/shared/research/2026-01-05-test.md"]

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return (
                "Done.",
                "new-session",
                tracker,
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
            return (
                "What framework should I use?",
                "new-session",
                SessionWriteTracker(),
            )

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

        # Create tracker with tracked write
        tracker = SessionWriteTracker()
        tracker.writes["research"] = ["thoughts/shared/research/2026-01-05-test.md"]

        @workflow_tool(
            Command.RESEARCH_CODEBASE, phase_name="Research", doc_type="research"
        )
        def research_tool(**kwargs):
            return (
                "Research complete.",
                "sess-1",
                tracker,
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
