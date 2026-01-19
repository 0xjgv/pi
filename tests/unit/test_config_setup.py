"""Tests for π.config logging setup functions."""

from pathlib import Path
from unittest.mock import patch

from π.config import get_logs_dir, setup_logging


class TestGetLogsDir:
    """Tests for get_logs_dir function."""

    def test_returns_path(self, tmp_path: Path):
        """Should return a Path object."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = tmp_path
            logs_dir = get_logs_dir()

        assert isinstance(logs_dir, Path)
        assert logs_dir.exists()

    def test_creates_directory(self, tmp_path: Path):
        """Should create the logs directory."""
        with patch("π.config.get_project_root") as mock_root:
            mock_root.return_value = tmp_path
            logs_dir = get_logs_dir()

        assert logs_dir.exists()
        assert logs_dir.is_dir()


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_log_file(self, tmp_path: Path):
        """Should return path to log file."""
        log_path = setup_logging(tmp_path, verbose=False)

        assert isinstance(log_path, Path)
        assert log_path.suffix == ".log"

    def test_verbose_mode(self, tmp_path: Path):
        """Should accept verbose flag."""
        log_path = setup_logging(tmp_path, verbose=True)

        assert isinstance(log_path, Path)
