"""Tests for π.cli.display module."""

from π.cli.display import LiveObserver, _format_tool_name


class TestFormatToolName:
    """Tests for _format_tool_name function."""

    def test_strips_mcp_workflow_prefix(self):
        """Should strip mcp__workflow__ prefix."""
        result = _format_tool_name("mcp__workflow__research_codebase")
        assert result == "research_codebase"

    def test_strips_mcp_prefix(self):
        """Should strip mcp__ prefix."""
        result = _format_tool_name("mcp__other__tool")
        assert result == "other__tool"

    def test_returns_name_unchanged(self):
        """Should return name unchanged if no prefix."""
        result = _format_tool_name("SomeTool")
        assert result == "SomeTool"


class TestLiveObserver:
    """Tests for LiveObserver class."""

    def test_initializes_empty_state(self):
        """Should initialize with empty state."""
        observer = LiveObserver()

        assert observer.current_tool is None
        assert observer.completed_tools == []
        assert observer.last_text == ""

    def test_on_tool_start_creates_tool_state(self):
        """Should create tool state on start."""
        observer = LiveObserver()
        observer.on_tool_start("TestTool", {"key": "value"})

        assert observer.current_tool is not None
        assert observer.current_tool.name == "TestTool"
        assert "key" in observer.current_tool.input_keys

    def test_on_tool_end_completes_tool(self):
        """Should complete current tool on end."""
        observer = LiveObserver()
        observer.on_tool_start("TestTool", {})
        observer.on_tool_end("TestTool", "result", is_error=False)

        assert observer.current_tool is None
        assert len(observer.completed_tools) == 1
        assert observer.completed_tools[0].status == "done"

    def test_on_tool_end_marks_error(self):
        """Should mark error status."""
        observer = LiveObserver()
        observer.on_tool_start("TestTool", {})
        observer.on_tool_end("TestTool", "error", is_error=True)

        assert observer.completed_tools[0].status == "error"

    def test_on_text_updates_last_text(self):
        """Should update last_text."""
        observer = LiveObserver()
        observer.on_text("Some text output")

        assert "Some text" in observer.last_text

    def test_ignores_stage_agent_events(self):
        """Should ignore non-orchestrator events."""
        observer = LiveObserver()
        observer.on_tool_start("TestTool", {}, agent_id="stage:research")

        # Should not create tool state for stage agent
        assert observer.current_tool is None
