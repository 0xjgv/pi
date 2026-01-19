"""Tests for π.workflow.observer module."""

from pathlib import Path
from unittest.mock import MagicMock

from π.workflow.observer import CompositeObserver, LoggingObserver


class TestLoggingObserver:
    """Tests for LoggingObserver class."""

    def test_creates_log_file(self, tmp_path: Path):
        """Should create log file with header."""
        log_path = tmp_path / "test.log"
        LoggingObserver(log_path, objective="test objective")

        assert log_path.exists()
        content = log_path.read_text()
        assert "test objective" in content
        assert "Workflow Log" in content

    def test_logs_tool_start(self, tmp_path: Path):
        """Should log tool start event."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_tool_start("TestTool", {"key": "value"})

        content = log_path.read_text()
        assert "TOOL_START: TestTool" in content

    def test_logs_tool_end(self, tmp_path: Path):
        """Should log tool end event."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_tool_end("TestTool", "result", is_error=False)

        content = log_path.read_text()
        assert "TOOL_END: TestTool [OK]" in content

    def test_logs_tool_end_error(self, tmp_path: Path):
        """Should log tool error."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_tool_end("TestTool", "error", is_error=True)

        content = log_path.read_text()
        assert "TOOL_END: TestTool [ERROR]" in content

    def test_logs_text(self, tmp_path: Path):
        """Should log text output."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_text("Test text output")

        content = log_path.read_text()
        assert "TEXT:" in content
        assert "Test text output" in content

    def test_logs_thinking(self, tmp_path: Path):
        """Should log thinking."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_thinking("Thinking about the problem")

        content = log_path.read_text()
        assert "THINKING:" in content

    def test_logs_complete(self, tmp_path: Path):
        """Should log completion with summary."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_complete(turns=5, cost=0.01, duration_ms=1000)

        content = log_path.read_text()
        assert "COMPLETE" in content
        assert "Turns: 5" in content
        assert "$0.01" in content

    def test_logs_system(self, tmp_path: Path):
        """Should log system messages."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_system("init", {"version": "1.0"})

        content = log_path.read_text()
        assert "SYSTEM_INIT:" in content

    def test_logs_with_agent_id(self, tmp_path: Path):
        """Should include agent_id in logs."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)
        observer.on_text("Test", agent_id="stage:research")

        content = log_path.read_text()
        assert "[stage:research]" in content


class TestCompositeObserver:
    """Tests for CompositeObserver class."""

    def test_dispatches_to_all_observers(self):
        """Should dispatch events to all observers."""
        obs1 = MagicMock()
        obs2 = MagicMock()
        composite = CompositeObserver([obs1, obs2])

        composite.on_tool_start("TestTool", {"key": "value"})

        obs1.on_tool_start.assert_called_once_with(
            "TestTool", {"key": "value"}, agent_id="orchestrator"
        )
        obs2.on_tool_start.assert_called_once_with(
            "TestTool", {"key": "value"}, agent_id="orchestrator"
        )

    def test_dispatches_tool_end(self):
        """Should dispatch tool end to all observers."""
        obs1 = MagicMock()
        composite = CompositeObserver([obs1])

        composite.on_tool_end("TestTool", "result", is_error=False)

        obs1.on_tool_end.assert_called_once()

    def test_dispatches_text(self):
        """Should dispatch text to all observers."""
        obs1 = MagicMock()
        composite = CompositeObserver([obs1])

        composite.on_text("Test text")

        obs1.on_text.assert_called_once()

    def test_dispatches_complete(self):
        """Should dispatch completion to all observers."""
        obs1 = MagicMock()
        composite = CompositeObserver([obs1])

        composite.on_complete(turns=5, cost=0.01, duration_ms=1000)

        obs1.on_complete.assert_called_once()

    def test_dispatches_thinking(self):
        """Should dispatch thinking to all observers."""
        obs1 = MagicMock()
        composite = CompositeObserver([obs1])

        composite.on_thinking("Thinking about this...", agent_id="stage:research")

        obs1.on_thinking.assert_called_once_with(
            "Thinking about this...", agent_id="stage:research"
        )

    def test_dispatches_system(self):
        """Should dispatch system to all observers."""
        obs1 = MagicMock()
        composite = CompositeObserver([obs1])

        composite.on_system("init", {"version": "1.0"}, agent_id="orchestrator")

        obs1.on_system.assert_called_once_with(
            "init", {"version": "1.0"}, agent_id="orchestrator"
        )


class TestDispatchMessage:
    """Tests for dispatch_message function."""

    def test_dispatch_result_message(self):
        """Should dispatch ResultMessage to on_complete."""
        from claude_agent_sdk.types import ResultMessage

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        message = MagicMock(spec=ResultMessage)
        message.num_turns = 5
        message.total_cost_usd = 0.01
        message.duration_ms = 1000

        dispatch_message(message, observer, agent_id="orchestrator")

        observer.on_complete.assert_called_once_with(
            turns=5, cost=0.01, duration_ms=1000, agent_id="orchestrator"
        )

    def test_dispatch_result_message_null_cost(self):
        """Should handle ResultMessage with null cost."""
        from claude_agent_sdk.types import ResultMessage

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        message = MagicMock(spec=ResultMessage)
        message.num_turns = 3
        message.total_cost_usd = None
        message.duration_ms = 500

        dispatch_message(message, observer)

        observer.on_complete.assert_called_once_with(
            turns=3, cost=0.0, duration_ms=500, agent_id="orchestrator"
        )

    def test_dispatch_system_message(self):
        """Should dispatch SystemMessage to on_system."""
        from claude_agent_sdk.types import SystemMessage

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        message = MagicMock(spec=SystemMessage)
        message.subtype = "init"
        message.data = {"session_id": "abc123"}

        dispatch_message(message, observer)

        observer.on_system.assert_called_once_with(
            subtype="init", data={"session_id": "abc123"}, agent_id="orchestrator"
        )

    def test_dispatch_assistant_text_block(self):
        """Should dispatch TextBlock to on_text."""
        from claude_agent_sdk.types import AssistantMessage, TextBlock

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        text_block = MagicMock(spec=TextBlock)
        text_block.text = "Hello world"

        message = MagicMock(spec=AssistantMessage)
        message.content = [text_block]

        dispatch_message(message, observer)

        observer.on_text.assert_called_once_with(
            text="Hello world", agent_id="orchestrator"
        )

    def test_dispatch_assistant_thinking_block(self):
        """Should dispatch ThinkingBlock to on_thinking."""
        from claude_agent_sdk.types import AssistantMessage, ThinkingBlock

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        thinking_block = MagicMock(spec=ThinkingBlock)
        thinking_block.thinking = "Let me think about this"

        message = MagicMock(spec=AssistantMessage)
        message.content = [thinking_block]

        dispatch_message(message, observer)

        observer.on_thinking.assert_called_once_with(
            text="Let me think about this", agent_id="orchestrator"
        )

    def test_dispatch_assistant_tool_use_block(self):
        """Should dispatch ToolUseBlock to on_tool_start."""
        from claude_agent_sdk.types import AssistantMessage, ToolUseBlock

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        tool_block = MagicMock(spec=ToolUseBlock)
        tool_block.name = "Read"
        tool_block.input = {"file_path": "/tmp/test.py"}

        message = MagicMock(spec=AssistantMessage)
        message.content = [tool_block]

        dispatch_message(message, observer, agent_id="stage:research")

        observer.on_tool_start.assert_called_once_with(
            name="Read",
            input={"file_path": "/tmp/test.py"},
            agent_id="stage:research",
        )

    def test_dispatch_tool_result_string(self):
        """Should dispatch ToolResultBlock with string content to on_tool_end."""
        from claude_agent_sdk.types import AssistantMessage, ToolResultBlock

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        result_block = MagicMock(spec=ToolResultBlock)
        result_block.content = "File contents here"
        result_block.tool_use_id = "tool-123"
        result_block.is_error = False

        message = MagicMock(spec=AssistantMessage)
        message.content = [result_block]

        dispatch_message(message, observer)

        observer.on_tool_end.assert_called_once_with(
            name="tool-123",
            result="File contents here",
            is_error=False,
            agent_id="orchestrator",
        )

    def test_dispatch_tool_result_list(self):
        """Should dispatch ToolResultBlock with list content to on_tool_end."""
        from claude_agent_sdk.types import AssistantMessage, ToolResultBlock

        from π.workflow.observer import dispatch_message

        observer = MagicMock()
        result_block = MagicMock(spec=ToolResultBlock)
        result_block.content = [{"type": "text", "text": "Result from list"}]
        result_block.tool_use_id = "tool-456"
        result_block.is_error = True

        message = MagicMock(spec=AssistantMessage)
        message.content = [result_block]

        dispatch_message(message, observer)

        observer.on_tool_end.assert_called_once_with(
            name="tool-456",
            result="Result from list",
            is_error=True,
            agent_id="orchestrator",
        )


class TestLoggingObserverOnSystem:
    """Tests for LoggingObserver.on_system method."""

    def test_logs_compact_boundary(self, tmp_path: Path):
        """Should log compact_boundary system event."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)

        observer.on_system(
            "compact_boundary",
            {"compact_metadata": {"trigger": "max_tokens", "pre_tokens": 50000}},
        )

        content = log_path.read_text()
        assert "SYSTEM_COMPACT" in content
        assert "trigger=max_tokens" in content
        assert "pre_tokens=50000" in content

    def test_logs_unknown_subtype(self, tmp_path: Path):
        """Should log unknown system subtype with uppercase name."""
        log_path = tmp_path / "test.log"
        observer = LoggingObserver(log_path)

        observer.on_system("custom_event", {"key": "value"})

        content = log_path.read_text()
        assert "SYSTEM_CUSTOM_EVENT:" in content
