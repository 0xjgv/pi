"""Tests for π.cli module."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from π.cli import AgentTask, main
from π.router import ExecutionMode


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
    def mock_workflow(self) -> Generator[dict[str, Any], None, None]:
        """Mock all workflow functions."""
        with (
            patch("π.cli.research_codebase") as mock_research,
            patch("π.cli.create_plan") as mock_plan,
            patch("π.cli.clarify_goal") as mock_clarify,
        ):
            yield {
                "research": mock_research,
                "plan": mock_plan,
                "clarify": mock_clarify,
            }

    @pytest.fixture
    def mock_router(self) -> Generator[MagicMock, None, None]:
        """Mock the router to return simple mode by default."""
        with patch("π.cli.classify_objective") as mock:
            mock.return_value = ExecutionMode.SIMPLE
            yield mock

    def test_requires_objective_argument(self, runner: CliRunner):
        """Should fail without objective argument."""
        result = runner.invoke(main, [])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "OBJECTIVE" in result.output

    def test_accepts_objective_argument(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should accept objective as positional argument."""
        result = runner.invoke(main, ["test objective"])

        assert result.exit_code == 0
        assert "test objective" in result.output

    def test_default_thinking_level_is_low(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should default to 'low' thinking level in simple mode."""
        with patch("π.cli.configure_dspy"):
            result = runner.invoke(main, ["test"])

        assert "claude/low" in result.output

    @pytest.mark.parametrize("level", ["low", "med", "high"])
    def test_accepts_thinking_levels(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
        level: str,
    ):
        """Should accept all valid thinking levels."""
        result = runner.invoke(main, ["test", "--thinking", level])

        assert result.exit_code == 0
        assert f"claude/{level}" in result.output

    def test_short_flag_for_thinking(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should accept -t as short flag for --thinking."""
        result = runner.invoke(main, ["test", "-t", "high"])

        assert result.exit_code == 0
        assert "claude/high" in result.output

    def test_rejects_invalid_thinking_level(self, runner: CliRunner):
        """Should reject invalid thinking levels."""
        result = runner.invoke(main, ["test", "-t", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_displays_final_answer(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should display the agent's final answer."""
        mock_dspy.ReAct.return_value.return_value = MagicMock(output="Agent result")

        result = runner.invoke(main, ["test objective"])

        assert "Final Answer:" in result.output

    def test_creates_react_agent_with_tools(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,
        mock_workflow: dict[str, Any],
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should create ReAct agent with workflow tools in simple mode."""
        runner.invoke(main, ["test"])

        mock_dspy.ReAct.assert_called_once()
        call_kwargs = mock_dspy.ReAct.call_args.kwargs

        # Should include our workflow tools
        tools = call_kwargs["tools"]
        assert mock_workflow["research"] in tools
        assert mock_workflow["plan"] in tools
        assert mock_workflow["clarify"] in tools

    def test_default_provider_is_claude(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should default to claude provider."""
        with patch("π.cli.configure_dspy"):
            result = runner.invoke(main, ["test"])

        assert "claude" in result.output.lower()

    @pytest.mark.parametrize("provider", ["claude", "antigravity"])
    def test_accepts_valid_providers(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
        provider: str,
    ):
        """Should accept valid provider values."""
        result = runner.invoke(main, ["test", "-p", provider])

        assert result.exit_code == 0
        assert provider in result.output.lower()

    def test_accepts_openai_provider(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should accept openai as a valid provider."""
        result = runner.invoke(main, ["test", "-p", "openai"])

        assert result.exit_code == 0
        assert "openai" in result.output.lower()

    def test_rejects_invalid_provider(self, runner: CliRunner):
        """Should reject invalid provider values."""
        result = runner.invoke(main, ["test", "-p", "invalid_provider"])

        assert result.exit_code != 0

    def test_provider_and_thinking_combine(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should combine provider and thinking options."""
        result = runner.invoke(main, ["test", "-p", "antigravity", "-t", "high"])

        assert result.exit_code == 0
        assert "antigravity" in result.output.lower()
        assert "high" in result.output.lower()


class TestModeOption:
    """Tests for --mode CLI option."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_workflow(self) -> Generator[dict[str, Any], None, None]:
        """Mock all workflow functions."""
        with (
            patch("π.cli.research_codebase") as mock_research,
            patch("π.cli.create_plan") as mock_plan,
            patch("π.cli.clarify_goal") as mock_clarify,
        ):
            yield {
                "research": mock_research,
                "plan": mock_plan,
                "clarify": mock_clarify,
            }

    @pytest.fixture
    def mock_router(self) -> Generator[MagicMock, None, None]:
        """Mock the router."""
        with patch("π.cli.classify_objective") as mock:
            mock.return_value = ExecutionMode.SIMPLE
            yield mock

    @pytest.fixture
    def mock_rpi_workflow(self) -> Generator[MagicMock, None, None]:
        """Mock RPIWorkflow."""
        with patch("π.cli.RPIWorkflow") as mock:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                clarified_objective="clarified",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                implementation_summary="done",
            )
            mock.return_value = mock_instance
            yield mock

    def test_auto_mode_calls_router(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,
    ):
        """Auto mode should call classify_objective."""
        runner.invoke(main, ["test", "-m", "auto"])

        mock_router.assert_called_once()

    def test_simple_mode_skips_router(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,
    ):
        """Forced simple mode should skip router."""
        runner.invoke(main, ["test", "-m", "simple"])

        mock_router.assert_not_called()

    def test_workflow_mode_skips_router(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Forced workflow mode should skip router."""
        runner.invoke(main, ["test", "-m", "workflow"])

        mock_router.assert_not_called()

    def test_workflow_mode_uses_rpi_workflow(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
        mock_rpi_workflow: MagicMock,
    ):
        """Workflow mode should use RPIWorkflow."""
        runner.invoke(main, ["test", "-m", "workflow"])

        mock_rpi_workflow.assert_called_once()

    def test_simple_mode_uses_react_agent(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Simple mode should use ReAct agent."""
        runner.invoke(main, ["test", "-m", "simple"])

        mock_dspy.ReAct.assert_called_once()

    def test_rejects_invalid_mode(self, runner: CliRunner):
        """Should reject invalid mode values."""
        result = runner.invoke(main, ["test", "-m", "invalid"])

        assert result.exit_code != 0

    def test_displays_forced_mode(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,  # noqa: ARG002
    ):
        """Should display forced mode in output."""
        result = runner.invoke(main, ["test", "-m", "simple"])

        assert "Forced mode: simple" in result.output

    def test_displays_router_selected_mode(
        self,
        runner: CliRunner,
        mock_dspy: MagicMock,  # noqa: ARG002
        mock_workflow: dict[str, Any],  # noqa: ARG002
        mock_router: MagicMock,
    ):
        """Should display router's mode selection."""
        mock_router.return_value = ExecutionMode.WORKFLOW

        with patch("π.cli.RPIWorkflow") as mock_rpi:
            mock_rpi.return_value.return_value = MagicMock(
                clarified_objective="goal",
                research_doc_path="/r.md",
                plan_doc_path="/p.md",
                implementation_summary="done",
            )
            result = runner.invoke(main, ["test", "-m", "auto"])

        assert "Router selected: workflow" in result.output
