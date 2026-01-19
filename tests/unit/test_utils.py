"""Tests for π.config module - logging setup."""

import logging

from π.config import get_logs_dir, setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_uses_provided_log_dir(self, tmp_path):
        """Should use the provided log directory."""
        logger = logging.getLogger("π")
        logger.handlers.clear()

        logs_dir = get_logs_dir(tmp_path)
        log_path = setup_logging(logs_dir)

        assert log_path.parent == tmp_path / ".π" / "logs"
        assert log_path.suffix == ".log"

    def test_always_sets_debug_level(self, tmp_path):
        """Logger should always be set to DEBUG level."""
        logger = logging.getLogger("π")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

        logs_dir = get_logs_dir(tmp_path)
        setup_logging(logs_dir)

        assert logging.getLogger("π").level == logging.DEBUG

    def test_delays_file_creation(self, tmp_path):
        """Log file should not exist until first message written."""
        logger = logging.getLogger("π")
        logger.handlers.clear()

        logs_dir = get_logs_dir(tmp_path)
        log_path = setup_logging(logs_dir)

        # File should NOT exist yet (delay=True)
        assert not log_path.exists()

        # Write a message
        logger.debug("test message")

        # Now file should exist
        assert log_path.exists()
        assert "test message" in log_path.read_text()

    def test_no_file_if_no_logging(self, tmp_path):
        """Log file should not be created if no messages logged."""
        logger = logging.getLogger("π")
        logger.handlers.clear()

        logs_dir = get_logs_dir(tmp_path)
        log_path = setup_logging(logs_dir)

        # Clear handlers without logging anything
        logger.handlers.clear()

        # File should never have been created
        assert not log_path.exists()

    def test_verbose_adds_console_handler(self, tmp_path):
        """setup_logging with verbose=True adds console handler."""
        logger = logging.getLogger("π")
        logger.handlers.clear()

        logs_dir = get_logs_dir(tmp_path)
        setup_logging(logs_dir, verbose=True)

        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "FileHandler" in handler_types

    def test_default_no_console_handler(self, tmp_path):
        """setup_logging without verbose does not add console handler."""
        logger = logging.getLogger("π")
        logger.handlers.clear()

        logs_dir = get_logs_dir(tmp_path)
        setup_logging(logs_dir)

        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" not in handler_types
        assert "FileHandler" in handler_types
