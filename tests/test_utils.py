"""Tests for π.utils module."""

import logging

from π.directory import get_logs_dir
from π.utils import setup_logging


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
