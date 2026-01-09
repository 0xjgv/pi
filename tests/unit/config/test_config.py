"""Tests for π.config module."""

from unittest.mock import MagicMock, patch

import pytest

from π.config import (
    DEFAULT_MODELS,
    PROVIDER_MODELS,
    Provider,
    get_lm,
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


class TestGetLm:
    """Tests for get_lm function."""

    @pytest.fixture(autouse=True)
    def clear_lru_cache(self):
        """Clear LRU cache before each test."""
        get_lm.cache_clear()
        yield
        get_lm.cache_clear()

    def test_returns_cached_lm(self, configured_env: None):
        """Should return cached LM instances."""
        with patch("π.core.models.dspy") as mock_dspy:
            mock_dspy.LM.return_value = MagicMock()

            lm1 = get_lm(Provider.Claude, "low")
            lm2 = get_lm(Provider.Claude, "low")

            assert lm1 is lm2
            mock_dspy.LM.assert_called_once()

    def test_different_tiers_return_different_lms(self, configured_env: None):
        """Different tiers should return different LM instances."""
        with patch("π.core.models.dspy") as mock_dspy:
            mock_dspy.LM.side_effect = [MagicMock(), MagicMock()]

            lm_low = get_lm(Provider.Claude, "low")
            lm_high = get_lm(Provider.Claude, "high")

            assert lm_low is not lm_high
            assert mock_dspy.LM.call_count == 2

    def test_uses_env_vars_for_api(self, configured_env: None):
        """Should use CLIPROXY_API_BASE and CLIPROXY_API_KEY from env."""
        with patch("π.core.models.dspy") as mock_dspy:
            mock_dspy.LM.return_value = MagicMock()

            get_lm(Provider.Claude, "low")

            call_kwargs = mock_dspy.LM.call_args
            assert call_kwargs.kwargs["api_base"] == "http://test:8317"
            assert call_kwargs.kwargs["api_key"] == "test-key"

    def test_defaults_to_localhost(self, clean_env: None):
        """Should default to localhost:8317 when no env var set."""
        with patch("π.core.models.dspy") as mock_dspy:
            mock_dspy.LM.return_value = MagicMock()

            get_lm(Provider.Claude, "low")

            call_kwargs = mock_dspy.LM.call_args
            assert "localhost:8317" in call_kwargs.kwargs["api_base"]


class TestProviderModels:
    """Tests for PROVIDER_MODELS configuration."""

    def test_all_providers_defined(self):
        """Should have models for all providers."""
        assert Provider.Claude in PROVIDER_MODELS
        assert Provider.Antigravity in PROVIDER_MODELS

    def test_claude_and_antigravity_have_all_tiers(self):
        """Claude and Antigravity providers should have low/med/high tiers."""
        for provider in [Provider.Claude, Provider.Antigravity]:
            assert "low" in PROVIDER_MODELS[provider]
            assert "med" in PROVIDER_MODELS[provider]
            assert "high" in PROVIDER_MODELS[provider]

    def test_all_providers_have_at_least_one_tier(self):
        """All providers should have at least one tier defined."""
        for provider in Provider:
            assert len(PROVIDER_MODELS[provider]) >= 1

    def test_claude_models_are_claude(self):
        """Claude provider should return Claude models."""
        for _tier, model in PROVIDER_MODELS[Provider.Claude].items():
            assert "claude" in model.lower()

    def test_antigravity_models_contain_gemini(self):
        """Antigravity provider should return Gemini-based models."""
        for _tier, model in PROVIDER_MODELS[Provider.Antigravity].items():
            assert "gemini" in model.lower()

    def test_raises_for_invalid_tier(self):
        """Should raise KeyError for invalid tier via PROVIDER_MODELS."""
        with pytest.raises(KeyError):
            _ = PROVIDER_MODELS[Provider.Claude]["invalid"]
