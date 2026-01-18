"""Tests for basic.bridge git utilities.

Tests verify that git helper functions return ground truth values
that the orchestrator can use for structured output.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from basic.bridge import get_git_changed_files, get_git_commit_hash


class TestGitCommitHash:
    """Tests for get_git_commit_hash function."""

    def test_returns_short_hash(self) -> None:
        """Test that function returns a short git hash."""
        with patch("basic.bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="abc1234\n",
            )
            result = get_git_commit_hash(cwd=Path("/test"))
            assert result == "abc1234"
            mock_run.assert_called_once()

    def test_returns_none_on_failure(self) -> None:
        """Test that function returns None if git fails."""
        with patch("basic.bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
            )
            result = get_git_commit_hash(cwd=Path("/test"))
            assert result is None


class TestGitChangedFiles:
    """Tests for get_git_changed_files function."""

    def test_returns_file_list(self) -> None:
        """Test that function returns list of changed files."""
        with patch("basic.bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="src/main.py\ntests/test_main.py\n",
            )
            result = get_git_changed_files(cwd=Path("/test"))
            assert result == ["src/main.py", "tests/test_main.py"]

    def test_returns_empty_on_failure(self) -> None:
        """Test that function returns empty list if git fails."""
        with patch("basic.bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
            )
            result = get_git_changed_files(cwd=Path("/test"))
            assert result == []

    def test_handles_empty_diff(self) -> None:
        """Test that function handles no changes."""
        with patch("basic.bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )
            result = get_git_changed_files(cwd=Path("/test"))
            assert result == []
