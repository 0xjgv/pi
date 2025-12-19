"""Tests for π.cli module."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from π.cli import AgentTask, main


class TestAgentTask:
    """Tests for AgentTask signature."""

    def test_is_dspy_signature(self):
        """Should be a DSPy Signature subclass."""
        import dspy

        assert issubclass(AgentTask, dspy.Signature)

    def test_has_docstring(self):
        """Should have a descriptive docstring."""
        assert AgentTask.__doc__ is not None
        assert (
            "objective" in AgentTask.__doc__.lower()
            or "tool" in AgentTask.__doc__.lower()
        )


class TestMain:
    """Tests for main CLI command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_workflow(self) -> MagicMock:
        """Mock all workflow functions."""
        with (
            patch("π.cli.research_codebase") as mock_research,
            patch("π.cli.create_plan") as mock_plan,
            patch("π.cli.implement_plan") as mock_impl,
            patch("π.cli.clarify_goal") as mock_clarify,
        ):
            yield {
                "research": mock_research,
                "plan": mock_plan,
                "implement": mock_impl,
                "clarify": mock_clarify,
            }

    def test_requires_objective_argument(self, runner: CliRunner):
        """Should fail without objective argument."""
        result = runner.invoke(main, [])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "OBJECTIVE" in result.output

    def test_accepts_objective_argument(
        self, runner: CliRunner, mock_dspy: MagicMock, mock_workflow: MagicMock
    ):
        """Should accept objective as positional argument."""
        result = runner.invoke(main, ["test objective"])

        assert result.exit_code == 0
        assert "test objective" in result.output

    def test_default_thinking_level_is_low(
        self, runner: CliRunner, mock_dspy: MagicMock, mock_workflow: MagicMock
    ):
        """Should default to 'low' thinking level."""
        with patch("π.cli.configure_dspy"):
            result = runner.invoke(main, ["test"])

        assert "[low]" in result.output

    @pytest.mark.parametrize("level", ["low", "med", "high"])
    def test_accepts_thinking_levels(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,
        mock_workflow: MagicMock,
        level: str,
    ):
        """Should accept all valid thinking levels."""
        result = runner.invoke(main, ["test", "--thinking", level])

        assert result.exit_code == 0
        assert f"[{level}]" in result.output

    def test_short_flag_for_thinking(
        self, runner: CliRunner, mock_dspy: MagicMock, mock_workflow: MagicMock
    ):
        """Should accept -t as short flag for --thinking."""
        result = runner.invoke(main, ["test", "-t", "high"])

        assert result.exit_code == 0
        assert "[high]" in result.output

    def test_rejects_invalid_thinking_level(self, runner: CliRunner):
        """Should reject invalid thinking levels."""
        result = runner.invoke(main, ["test", "-t", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_displays_final_answer(
        self, runner: CliRunner, mock_dspy: MagicMock, mock_workflow: MagicMock
    ):
        """Should display the agent's final answer."""
        mock_dspy.ReAct.return_value.return_value = MagicMock(output="Agent result")

        result = runner.invoke(main, ["test objective"])

        assert "Final Answer:" in result.output

    def test_creates_react_agent_with_tools(
        self, runner: CliRunner, mock_dspy: MagicMock, mock_workflow: MagicMock
    ):
        """Should create ReAct agent with workflow tools."""
        runner.invoke(main, ["test"])

        mock_dspy.ReAct.assert_called_once()
        call_kwargs = mock_dspy.ReAct.call_args.kwargs

        # Should include our workflow tools
        tools = call_kwargs["tools"]
        assert mock_workflow["research"] in tools
        assert mock_workflow["plan"] in tools
        assert mock_workflow["implement"] in tools
        assert mock_workflow["clarify"] in tools
