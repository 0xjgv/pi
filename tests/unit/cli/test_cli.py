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
        """Redirect logging to temp dir."""
        mock_logs_dir = tmp_path / ".π" / "logs"
        mock_logs_dir.mkdir(parents=True)
        with patch("π.cli.main.get_logs_dir", return_value=mock_logs_dir):
            yield

    @pytest.fixture
    def mock_run(self) -> Generator[MagicMock]:
        """Mock the async run function."""
        with patch("π.cli.main.asyncio.run") as mock:
            mock.return_value = MagicMock(
                status="complete",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                files_changed=["test.py"],
                commit_hash="abc1234",
                summary="Test complete",
            )
            yield mock

    def test_shows_help_without_objective(self, capsys: pytest.CaptureFixture[str]):
        """Should show help when no objective is provided."""
        main([])
        captured = capsys.readouterr()

        assert "objective" in captured.out.lower() or "usage" in captured.out.lower()

    def test_accepts_objective_argument(
        self,
        capsys: pytest.CaptureFixture[str],
        mock_run: MagicMock,
    ):
        """Should accept objective as positional argument."""
        main(["test objective"])

        # run() should be called with the objective
        mock_run.assert_called_once()

    def test_verbose_flag_accepted(
        self,
        mock_run: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        """--verbose flag should be accepted."""
        main(["--verbose", "test objective"])

        # Should complete without error
        mock_run.assert_called_once()
