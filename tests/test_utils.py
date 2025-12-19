"""Tests for π.utils module."""

import logging

from π.utils import setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_always_sets_debug_level(self):
        """Logger should always be set to DEBUG level."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        setup_logging()
        assert logging.getLogger("π").level == logging.DEBUG

    def test_returns_log_path(self, tmp_path, monkeypatch):
        """Should return the log file path."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        log_path = setup_logging()

        assert log_path is not None
        assert log_path.parent == tmp_path / ".π" / "logs"
        assert log_path.suffix == ".log"
