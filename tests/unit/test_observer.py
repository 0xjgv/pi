"""Tests for π.observer module."""

from pathlib import Path
from unittest.mock import MagicMock

from π.observer import CompositeObserver, LoggingObserver


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
