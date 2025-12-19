"""Tests for π.config module."""

import logging
from unittest.mock import MagicMock

from π.config import THINKING_MODELS, configure_dspy


class TestThinkingModels:
    """Tests for THINKING_MODELS constant."""

    def test_contains_all_levels(self):
        """Should have low, med, high levels."""
        assert "low" in THINKING_MODELS
        assert "med" in THINKING_MODELS
        assert "high" in THINKING_MODELS

    def test_models_are_strings(self):
        """All model values should be strings."""
        for level, model in THINKING_MODELS.items():
            assert isinstance(model, str), f"{level} model is not a string"

    def test_models_contain_claude(self):
        """All models should be Claude models."""
        for level, model in THINKING_MODELS.items():
            assert "claude" in model.lower(), f"{level} model doesn't contain 'claude'"


class TestConfigureDspy:
    """Tests for configure_dspy function."""

    def test_configures_with_default_model(self, mock_dspy_configure: MagicMock):
        """Should configure DSPy with the provided model."""
        logger = logging.getLogger("test")

        configure_dspy(model="claude-haiku-4-5-20251001", logger=logger)

        mock_dspy_configure.LM.assert_called_once()
        mock_dspy_configure.configure.assert_called_once()

    def test_uses_env_vars_for_api(
        self, mock_dspy_configure: MagicMock, configured_env: None
    ):
        """Should use CLIPROXY_API_BASE and CLIPROXY_API_KEY from env."""
        logger = logging.getLogger("test")

        configure_dspy(model="test-model", logger=logger)

        call_kwargs = mock_dspy_configure.LM.call_args
        assert call_kwargs.kwargs["api_base"] == "http://test:8317"
        assert call_kwargs.kwargs["api_key"] == "test-key"

    def test_logs_warning_on_exception(self, mock_dspy_configure: MagicMock):
        """Should log warning when DSPy configuration fails."""
        mock_dspy_configure.LM.side_effect = Exception("Connection failed")
        logger = MagicMock(spec=logging.Logger)

        # Should not raise
        configure_dspy(model="test-model", logger=logger)

        logger.warning.assert_called_once()
        assert "DSPy LM not configured" in logger.warning.call_args[0][0]

    def test_defaults_to_localhost(
        self, mock_dspy_configure: MagicMock, clean_env: None
    ):
        """Should default to localhost:8317 when no env var set."""
        logger = logging.getLogger("test")

        configure_dspy(model="test-model", logger=logger)

        call_kwargs = mock_dspy_configure.LM.call_args
        assert "localhost:8317" in call_kwargs.kwargs["api_base"]
