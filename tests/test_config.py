"""Tests for π.config module."""

import logging
from unittest.mock import MagicMock

import pytest

from π.config import (
    DEFAULT_MODELS,
    PROVIDER_MODELS,
    Provider,
    configure_dspy,
    get_model,
)


class TestThinkingModels:
    """Tests for THINKING_MODELS constant."""

    def test_contains_all_levels(self):
        """Should have low, med, high levels."""
        assert "low" in DEFAULT_MODELS
        assert "med" in DEFAULT_MODELS
        assert "high" in DEFAULT_MODELS

    def test_models_are_strings(self):
        """All model values should be strings."""
        for level, model in DEFAULT_MODELS.items():
            assert isinstance(model, str), f"{level} model is not a string"

    def test_models_contain_claude(self):
        """All models should be Claude models."""
        for level, model in DEFAULT_MODELS.items():
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


class TestProviderModels:
    """Tests for PROVIDER_MODELS configuration."""

    def test_all_providers_defined(self):
        """Should have models for all providers."""
        assert Provider.Claude in PROVIDER_MODELS
        assert Provider.Gemini in PROVIDER_MODELS

    def test_all_tiers_per_provider(self):
        """Each provider should have low/med/high tiers."""
        for provider in Provider:
            assert "low" in PROVIDER_MODELS[provider]
            assert "med" in PROVIDER_MODELS[provider]
            assert "high" in PROVIDER_MODELS[provider]

    def test_claude_models_are_claude(self):
        """Claude provider should return Claude models."""
        for tier, model in PROVIDER_MODELS[Provider.Claude].items():
            assert "claude" in model.lower()

    def test_gemini_models_are_gemini(self):
        """Gemini provider should return Gemini models."""
        for tier, model in PROVIDER_MODELS[Provider.Gemini].items():
            assert "gemini" in model.lower()


class TestGetModel:
    """Tests for get_model function."""

    def test_returns_claude_haiku_for_claude_low(self):
        """Should return Haiku for Claude low tier."""
        model = get_model(provider=Provider.Claude, tier="low")
        assert "haiku" in model.lower()

    def test_returns_gemini_pro_for_gemini_high(self):
        """Should return Pro for Gemini high tier."""
        model = get_model(provider=Provider.Gemini, tier="high")
        assert "pro" in model.lower()

    def test_raises_for_invalid_tier(self):
        """Should raise KeyError for invalid tier."""
        with pytest.raises(KeyError):
            get_model(provider=Provider.Claude, tier="invalid")
