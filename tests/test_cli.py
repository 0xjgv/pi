"""Tests for π.cli module."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from π.cli import main


class TestMain:
    """Tests for main CLI command."""

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

    def test_shows_help_without_objective(self, capsys: pytest.CaptureFixture[str]):
        """Should show help when no objective is provided."""
        main([])
        captured = capsys.readouterr()

        assert "objective" in captured.out.lower() or "usage" in captured.out.lower()

    def test_accepts_objective_argument(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should accept objective as positional argument."""
        main(["test objective"])
        captured = capsys.readouterr()

        # Should not show help, should run workflow
        assert "Workflow Mode" in captured.out

    def test_runs_workflow_mode(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should run workflow mode with objective."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "Workflow Mode" in captured.out

    def test_uses_claude_provider(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,
    ):
        """Should use Claude provider."""
        main(["test"])
        captured = capsys.readouterr()

        mock_rpi_workflow.assert_called_once()
        # Claude provider is displayed in output
        assert "claude" in captured.out.lower()

    def test_displays_workflow_completion(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_rpi_workflow: MagicMock,  # noqa: ARG002
    ):
        """Should display workflow completion message."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "Workflow Complete" in captured.out
        assert "Research Doc" in captured.out
        assert "Plan Doc" in captured.out
