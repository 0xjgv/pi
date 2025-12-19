"""Tests for π.utils module."""

import logging

import pytest

from π.utils import setup_logging


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

    def test_default_sets_info_level(self):
        """Default mode should set INFO level."""
        setup_logging(verbose=False)
        assert logging.getLogger("π").level == logging.INFO

    def test_returns_logger_instance(self):
        """Should return a configured logger instance."""
        logger = setup_logging(verbose=False)

        assert logger is not None
        assert logger.name == "π"

    def test_configures_root_logger(self):
        """Should configure root logger via basicConfig."""
        setup_logging(verbose=False)

        # Root logger should have at least one handler from basicConfig
        assert len(logging.root.handlers) > 0

    def test_silences_noisy_loggers(self):
        """Should silence third-party loggers."""
        setup_logging(verbose=False)

        for name in ("httpcore", "httpx", "claude_agent_sdk"):
            assert logging.getLogger(name).level == logging.WARNING
