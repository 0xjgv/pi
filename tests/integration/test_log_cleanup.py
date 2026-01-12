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

        # Mock the workflow execution to avoid actual agent run
        with patch("π.cli.main.StagedWorkflow") as mock_workflow:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                status="success",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock_workflow.return_value = mock_instance

            main(["test objective"])
            captured = capsys.readouterr()

        # Verify cleanup occurred
        assert "Workflow Mode" in captured.out
        assert not old_log.exists(), "Old log should be deleted"
        assert recent_log.exists(), "Recent log should be preserved"

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

        # Mock the workflow execution
        with patch("π.cli.main.StagedWorkflow") as mock_workflow:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(
                status="success",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
            )
            mock_workflow.return_value = mock_instance

            main(["test objective"])
            captured = capsys.readouterr()

        # Should complete successfully with no errors
        assert "Workflow Mode" in captured.out
