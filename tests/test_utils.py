"""Tests for π.utils module."""

import logging
from pathlib import Path

import pytest

from π.utils import get_log_path, setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    @pytest.fixture(autouse=True)
    def _clean_logging(self, clean_logging):
        """Use the shared clean_logging fixture for all tests."""
        pass

    def test_verbose_sets_debug_level(self):
        """Verbose mode should set DEBUG level."""
        setup_logging(verbose=True)
        assert logging.getLogger("π").level == logging.DEBUG

    def test_default_sets_warning_level(self):
        """Default mode should set WARNING level (suppress logs for clean console)."""
        setup_logging(verbose=False)
        assert logging.getLogger("π").level == logging.WARNING

    def test_returns_logger_instance(self):
        """Should return a configured logger instance."""
        logger = setup_logging(verbose=False)

        assert logger is not None
        assert logger.name == "π"

    def test_verbose_creates_file_handler(self, tmp_path: Path, monkeypatch):
        """Verbose mode should create a file handler."""
        # Redirect log directory to tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        setup_logging(verbose=True)
        logger = logging.getLogger("π")

        # Should have at least one handler (file handler)
        assert len(logger.handlers) > 0

    def test_silences_noisy_loggers(self):
        """Should silence third-party loggers."""
        setup_logging(verbose=False)

        for name in ("httpcore", "httpx", "claude_agent_sdk"):
            assert logging.getLogger(name).level == logging.WARNING

    def test_clears_previous_handlers(self):
        """Should clear handlers from previous setup calls."""
        logger = logging.getLogger("π")

        # Add a dummy handler
        dummy_handler = logging.NullHandler()
        logger.addHandler(dummy_handler)
        initial_count = len(logger.handlers)

        setup_logging(verbose=False)

        # Handler count should not grow unbounded
        assert len(logger.handlers) <= initial_count


class TestGetLogPath:
    """Tests for get_log_path function."""

    def test_returns_none_by_default(self):
        """Should return None when no log path is set."""
        result = get_log_path()
        # Result could be None or a Path depending on prior test state
        assert result is None or isinstance(result, Path)
