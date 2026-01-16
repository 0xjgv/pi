"""Tests for π.config module."""

from unittest.mock import MagicMock, patch

import pytest

from π.config import (
    TIER_TO_MODEL,
    Tier,
    get_lm,
)


class TestClaudeModels:
    """Tests for Claude model tiers."""

    def test_contains_all_tiers(self):
        """Should have low, med, high tiers."""
        assert Tier.LOW in TIER_TO_MODEL
        assert Tier.MED in TIER_TO_MODEL
        assert Tier.HIGH in TIER_TO_MODEL

    def test_models_are_strings(self):
        """All model values should be strings."""
        for tier, model in TIER_TO_MODEL.items():
            assert isinstance(model, str), f"{tier} model is not a string"

    def test_models_contain_claude(self):
        """All models should be Claude models."""
        for tier, model in TIER_TO_MODEL.items():
            assert "claude" in model.lower(), f"{tier} model doesn't contain 'claude'"


class TestGetLm:
    """Tests for get_lm function."""

    @pytest.fixture(autouse=True)
    def clear_lru_cache(self):
        """Clear LRU cache before each test."""
        get_lm.cache_clear()
        yield
        get_lm.cache_clear()

    def test_returns_cached_lm(self):
        """Should return cached LM instances."""
        with patch("π.bridge.lm.ClaudeCodeLM") as mock_claude_code_lm:
            mock_claude_code_lm.return_value = MagicMock()

            lm1 = get_lm(Tier.LOW)
            lm2 = get_lm(Tier.LOW)

            assert lm1 is lm2
            mock_claude_code_lm.assert_called_once()

    def test_different_tiers_return_different_lms(self):
        """Different tiers should return different LM instances."""
        with patch("π.bridge.lm.ClaudeCodeLM") as mock_claude_code_lm:
            mock_claude_code_lm.side_effect = [MagicMock(), MagicMock()]

            lm_low = get_lm(Tier.LOW)
            lm_high = get_lm(Tier.HIGH)

            assert lm_low is not lm_high
            assert mock_claude_code_lm.call_count == 2


class TestTierToModel:
    """Tests for TIER_TO_MODEL configuration."""

    def test_all_tiers_have_models(self):
        """All tiers should have model mappings."""
        assert Tier.LOW in TIER_TO_MODEL
        assert Tier.MED in TIER_TO_MODEL
        assert Tier.HIGH in TIER_TO_MODEL

    def test_models_are_claude(self):
        """All models should be Claude models."""
        for _tier, model in TIER_TO_MODEL.items():
            assert "claude" in model.lower()

    def test_raises_for_invalid_tier(self):
        """Should raise KeyError for invalid tier."""
        with pytest.raises(KeyError):
            _ = TIER_TO_MODEL["invalid"]  # type: ignore[index]
