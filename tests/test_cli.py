"""Tests for π.cli module."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from π.cli import main


class TestMain:
    """Tests for main CLI command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_rpi_workflow(self) -> Generator[MagicMock, None, None]:
        """Mock RPIWorkflow."""
        with patch("π.cli.RPIWorkflow") as mock:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock.return_value = mock_instance
            yield mock

    def test_shows_help_without_objective(self, runner: CliRunner):
        """Should show help when no objective is provided."""
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "OBJECTIVE" in result.output or "Usage:" in result.output

    def test_accepts_objective_argument(
        self,
        runner: CliRunner,
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should accept objective as positional argument."""
        result = runner.invoke(main, ["test objective"])

        assert result.exit_code == 0

    def test_runs_workflow_mode(
        self,
        runner: CliRunner,
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should run workflow mode with objective."""
        result = runner.invoke(main, ["test objective"])

        assert result.exit_code == 0
        assert "Workflow Mode" in result.output

    def test_uses_claude_provider(
        self,
        runner: CliRunner,
        mock_rpi_workflow: MagicMock,
    ):
        """Should use Claude provider."""
        result = runner.invoke(main, ["test"])

        mock_rpi_workflow.assert_called_once()
        # Claude provider is displayed in output
        assert "claude" in result.output

    def test_displays_workflow_completion(
        self,
        runner: CliRunner,
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should display workflow completion message."""
        result = runner.invoke(main, ["test objective"])

        assert "Workflow Complete" in result.output
        assert "Research Doc" in result.output
        assert "Plan Doc" in result.output
