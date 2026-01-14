"""Tests for doc_sync CLI entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from π.doc_sync.__main__ import (
    count_files_in_commit,
    get_current_commit,
    get_git_diff,
    main,
    read_claude_md,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestGitHelpers:
    """Tests for git helper functions."""

    @patch("π.doc_sync.__main__.subprocess.run")
    @patch("π.doc_sync.__main__.get_project_root")
    def test_get_git_diff_without_commit(
        self,
        mock_root: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """get_git_diff without commit runs git diff --stat."""
        mock_root.return_value = tmp_path
        mock_run.return_value = MagicMock(stdout="file.py | 10 ++++")

        result = get_git_diff()

        assert result == "file.py | 10 ++++"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["git", "diff", "--stat"]

    @patch("π.doc_sync.__main__.subprocess.run")
    @patch("π.doc_sync.__main__.get_project_root")
    def test_get_git_diff_with_commit(
        self,
        mock_root: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """get_git_diff with commit includes commit range."""
        mock_root.return_value = tmp_path
        mock_run.return_value = MagicMock(stdout="file.py | 5 ++")

        result = get_git_diff(since_commit="abc123")

        assert result == "file.py | 5 ++"
        cmd = mock_run.call_args[0][0]
        assert "abc123..HEAD" in cmd

    @patch("π.doc_sync.__main__.subprocess.run")
    @patch("π.doc_sync.__main__.get_project_root")
    def test_get_current_commit(
        self,
        mock_root: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """get_current_commit returns stripped commit hash."""
        mock_root.return_value = tmp_path
        mock_run.return_value = MagicMock(stdout="abc123def\n")

        result = get_current_commit()

        assert result == "abc123def"
        cmd = mock_run.call_args[0][0]
        assert cmd == ["git", "rev-parse", "HEAD"]

    @patch("π.doc_sync.__main__.subprocess.run")
    @patch("π.doc_sync.__main__.get_project_root")
    def test_count_files_in_commit(
        self,
        mock_root: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """count_files_in_commit counts files from git diff."""
        mock_root.return_value = tmp_path
        mock_run.return_value = MagicMock(stdout="file1.py\nfile2.py\nfile3.py\n")

        result = count_files_in_commit()

        assert result == 3
        cmd = mock_run.call_args[0][0]
        assert cmd == ["git", "diff", "--name-only", "HEAD~1", "HEAD"]

    @patch("π.doc_sync.__main__.subprocess.run")
    @patch("π.doc_sync.__main__.get_project_root")
    def test_count_files_in_commit_empty(
        self,
        mock_root: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """count_files_in_commit returns 0 for empty output."""
        mock_root.return_value = tmp_path
        mock_run.return_value = MagicMock(stdout="")

        result = count_files_in_commit()

        assert result == 0

    @patch("π.doc_sync.__main__.get_project_root")
    def test_read_claude_md_exists(
        self,
        mock_root: MagicMock,
        tmp_path: Path,
    ) -> None:
        """read_claude_md returns content when file exists."""
        mock_root.return_value = tmp_path
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project\nDescription here.")

        result = read_claude_md()

        assert result == "# Project\nDescription here."

    @patch("π.doc_sync.__main__.get_project_root")
    def test_read_claude_md_missing(
        self,
        mock_root: MagicMock,
        tmp_path: Path,
    ) -> None:
        """read_claude_md returns empty string when file missing."""
        mock_root.return_value = tmp_path

        result = read_claude_md()

        assert result == ""


class TestMainEntryPoint:
    """Tests for main() function."""

    @patch("π.doc_sync.__main__.DocSyncState")
    @patch("π.doc_sync.__main__.count_files_in_commit")
    def test_accumulate_only_increments_count(
        self,
        mock_count: MagicMock,
        mock_state_class: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--accumulate-only increments file count and saves."""
        monkeypatch.setattr("sys.argv", ["doc_sync", "--accumulate-only"])

        mock_state = MagicMock()
        mock_state.files_changed_since_sync = 5
        mock_state.files_threshold = 10
        mock_state_class.load.return_value = mock_state
        mock_count.return_value = 3

        result = main()

        assert result == 0
        assert mock_state.files_changed_since_sync == 8  # 5 + 3
        mock_state.save.assert_called_once()

    @patch("π.doc_sync.__main__.DocSyncState")
    def test_skip_when_below_threshold(
        self,
        mock_state_class: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Skips sync when below threshold without --force."""
        monkeypatch.setattr("sys.argv", ["doc_sync"])

        mock_state = MagicMock()
        mock_state.should_trigger.return_value = False
        mock_state_class.load.return_value = mock_state

        result = main()

        assert result == 0
        mock_state.mark_synced.assert_not_called()

    @patch("π.doc_sync.__main__.stage_doc_sync")
    @patch("π.doc_sync.__main__.get_lm")
    @patch("π.doc_sync.__main__.read_claude_md")
    @patch("π.doc_sync.__main__.get_git_diff")
    @patch("π.doc_sync.__main__.DocSyncState")
    def test_force_overrides_threshold(
        self,
        mock_state_class: MagicMock,
        mock_diff: MagicMock,
        mock_read: MagicMock,
        mock_get_lm: MagicMock,
        mock_stage: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--force runs sync regardless of threshold."""
        monkeypatch.setattr("sys.argv", ["doc_sync", "--force"])

        mock_state = MagicMock()
        mock_state.should_trigger.return_value = False  # Below threshold
        mock_state.last_sync_commit = None
        mock_state_class.load.return_value = mock_state
        mock_diff.return_value = "file.py | 10 ++++"
        mock_read.return_value = "# Project"
        mock_stage.return_value = MagicMock(updated=False)

        result = main()

        assert result == 0
        mock_stage.assert_called_once()  # Agent was run despite threshold

    @patch("π.doc_sync.__main__.get_current_commit")
    @patch("π.doc_sync.__main__.stage_doc_sync")
    @patch("π.doc_sync.__main__.get_lm")
    @patch("π.doc_sync.__main__.read_claude_md")
    @patch("π.doc_sync.__main__.get_git_diff")
    @patch("π.doc_sync.__main__.DocSyncState")
    def test_runs_agent_when_threshold_met(
        self,
        mock_state_class: MagicMock,
        mock_diff: MagicMock,
        mock_read: MagicMock,
        mock_get_lm: MagicMock,
        mock_stage: MagicMock,
        mock_commit: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Runs agent when threshold is met."""
        monkeypatch.setattr("sys.argv", ["doc_sync"])

        mock_state = MagicMock()
        mock_state.should_trigger.return_value = True
        mock_state.last_sync_commit = None
        mock_state_class.load.return_value = mock_state
        mock_diff.return_value = "file.py | 10 ++++"
        mock_read.return_value = "# Project"
        mock_stage.return_value = MagicMock(updated=True)
        mock_commit.return_value = "abc123"

        result = main()

        assert result == 0
        mock_stage.assert_called_once()
        mock_state.mark_synced.assert_called_once_with("abc123")

    @patch("π.doc_sync.__main__.get_git_diff")
    @patch("π.doc_sync.__main__.DocSyncState")
    def test_no_changes_exits_early(
        self,
        mock_state_class: MagicMock,
        mock_diff: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exits early when no git changes detected."""
        monkeypatch.setattr("sys.argv", ["doc_sync", "--force"])

        mock_state = MagicMock()
        mock_state.should_trigger.return_value = True
        mock_state.last_sync_commit = None
        mock_state_class.load.return_value = mock_state
        mock_diff.return_value = ""  # No changes

        result = main()

        assert result == 0
        mock_state.mark_synced.assert_not_called()
