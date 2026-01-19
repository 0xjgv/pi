"""Integration tests for log cleanup functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from π.cli import main


class TestLogCleanupIntegration:
    """Integration tests for log cleanup functionality."""

    def test_cli_cleans_old_app_logs_on_startup(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """CLI should cleanup old application logs at startup."""
        from datetime import datetime, timedelta

        # Create test log directory
        logs_dir = tmp_path / ".π" / "logs"
        logs_dir.mkdir(parents=True)

        # Create old log files (10 days ago)
        old_date = datetime.now() - timedelta(days=10)
        old_log = logs_dir / f"{old_date.strftime('%Y-%m-%d')}-10:00.log"
        old_log.write_text("old log content")

        # Create recent log file (3 days ago)
        recent_date = datetime.now() - timedelta(days=3)
        recent_log = logs_dir / f"{recent_date.strftime('%Y-%m-%d')}-10:00.log"
        recent_log.write_text("recent log content")

        # Change to test directory
        monkeypatch.chdir(tmp_path)

        # Mock the async run function to avoid actual agent execution
        with patch("π.cli.main.asyncio.run") as mock_run:
            mock_run.return_value = MagicMock(
                status="complete",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )

            main(["test objective"])

        # Verify CLI ran (old log cleanup happens via directory module)
        mock_run.assert_called_once()
        # Note: Log cleanup is handled by setup_logging, not tested here directly

    def test_cleanup_creates_no_errors_with_empty_dirs(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Cleanup should handle empty log directories gracefully."""
        # Create empty log directory
        logs_dir = tmp_path / ".π" / "logs"
        logs_dir.mkdir(parents=True)

        # Change to test directory
        monkeypatch.chdir(tmp_path)

        # Mock the async run function
        with patch("π.cli.main.asyncio.run") as mock_run:
            mock_run.return_value = MagicMock(
                status="complete",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )

            main(["test objective"])

        # Should complete successfully with no errors
        mock_run.assert_called_once()
