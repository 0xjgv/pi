"""Tests for π.utils module."""

import logging

from π.utils import setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_verbose_sets_debug_level(self):
        """Verbose mode should set DEBUG level."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=True)
        assert logging.getLogger("π").level == logging.DEBUG

    def test_default_sets_info_level(self):
        """Default mode should set INFO level."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=False)
        assert logging.getLogger("π").level == logging.INFO
