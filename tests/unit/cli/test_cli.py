"""Tests for π.cli module."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from π.cli import main


class TestMain:
    """Tests for main CLI command."""

    @pytest.fixture(autouse=True)
    def isolate_logging(self, tmp_path: Path) -> Generator[None]:
        """Redirect logging to temp dir and disable checkpoints."""
        mock_logs_dir = tmp_path / ".π" / "logs"
        mock_logs_dir.mkdir(parents=True)
        with (
            patch("π.cli.main.get_logs_dir", return_value=mock_logs_dir),
            patch("π.workflow.checkpoint.get_project_root", return_value=tmp_path),
        ):
            yield

    @pytest.fixture
    def mock_staged_workflow(self) -> Generator[MagicMock]:
        """Mock StagedWorkflow."""
        with patch("π.cli.main.StagedWorkflow") as mock:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                status="success",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                files_changed=["test.py"],
                commit_hash="abc1234",
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
        mock_staged_workflow: MagicMock,
    ):
        """Should accept objective as positional argument."""
        main(["test objective"])
        captured = capsys.readouterr()

        # Should not show help, should run workflow
        assert "π Workflow" in captured.out

    def test_runs_workflow_mode(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_staged_workflow: MagicMock,
    ):
        """Should run workflow mode with objective."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "π Workflow" in captured.out

    def test_uses_claude_provider(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_staged_workflow: MagicMock,
    ):
        """Should use Claude provider."""
        main(["test"])
        captured = capsys.readouterr()

        mock_staged_workflow.assert_called_once()
        # Claude provider is displayed in output
        assert "claude" in captured.out.lower()

    def test_displays_workflow_completion(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_staged_workflow: MagicMock,
    ):
        """Should display workflow completion message."""
        main(["test objective"])
        captured = capsys.readouterr()

        assert "Workflow Complete" in captured.out
        assert "Status: success" in captured.out

    def test_verbose_flag_sets_pi_lm_debug(
        self,
        mock_staged_workflow: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """--verbose flag should set PI_LM_DEBUG env var."""
        # Clear any existing value
        monkeypatch.delenv("PI_LM_DEBUG", raising=False)

        import os

        main(["--verbose", "test objective"])

        # Fixture used to allow workflow to run
        assert mock_staged_workflow is not None
        assert os.environ.get("PI_LM_DEBUG") == "1"
