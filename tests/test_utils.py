"""Tests for π.utils module."""

import logging
from pathlib import Path

import π.utils
from π.utils import setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_always_sets_debug_level(self, tmp_path, monkeypatch):
        """Logger should always be set to DEBUG level."""
        # Clear any existing handlers
        logger = logging.getLogger("π")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

        # Mock __file__ to redirect log directory to temp path
        fake_file = tmp_path / "π" / "utils.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        monkeypatch.setattr(π.utils, "__file__", str(fake_file))

        setup_logging()
        assert logging.getLogger("π").level == logging.DEBUG

    def test_returns_log_path(self, tmp_path, monkeypatch):
        """Should return the log file path."""
        # Mock __file__ to redirect log directory to temp path
        fake_file = tmp_path / "π" / "utils.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        monkeypatch.setattr(π.utils, "__file__", str(fake_file))

        log_path = setup_logging()

        assert log_path is not None
        assert log_path.parent == tmp_path / ".logs"
        assert log_path.suffix == ".log"

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        """Should create the log directory if it doesn't exist."""
        fake_file = tmp_path / "π" / "utils.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        fake_file.touch()
        monkeypatch.setattr(π.utils, "__file__", str(fake_file))

        log_path = setup_logging()

        assert log_path.parent.exists()
        assert log_path.parent.is_dir()
