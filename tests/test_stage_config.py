"""Tests for π.stage_config module."""

import dataclasses

import pytest

from π.stage_config import DEFAULT_STAGE_CONFIGS, Stage, StageConfig


class TestStage:
    """Tests for Stage enum."""

    def test_has_all_workflow_stages(self):
        """Should define all five workflow stages."""
        assert Stage.CLARIFY == "clarify"
        assert Stage.RESEARCH == "research"
        assert Stage.PLAN == "plan"
        assert Stage.REVIEW_PLAN == "review_plan"
        assert Stage.IMPLEMENT == "implement"

    def test_stage_count(self):
        """Should have exactly 5 stages."""
        assert len(Stage) == 5

    def test_stages_are_strings(self):
        """Stage values should be strings for serialization."""
        for stage in Stage:
            assert isinstance(stage.value, str)


class TestStageConfig:
    """Tests for StageConfig dataclass."""

    def test_creates_with_required_fields(self):
        """Should create config with model_tier and max_iters."""
        config = StageConfig(model_tier="high", max_iters=5)

        assert config.model_tier == "high"
        assert config.max_iters == 5

    def test_description_defaults_to_empty(self):
        """Description should default to empty string."""
        config = StageConfig(model_tier="low", max_iters=3)

        assert config.description == ""

    def test_accepts_description(self):
        """Should accept optional description."""
        config = StageConfig(
            model_tier="med",
            max_iters=3,
            description="Test description",
        )

        assert config.description == "Test description"

    def test_is_frozen(self):
        """StageConfig should be immutable."""
        config = StageConfig(model_tier="low", max_iters=3)

        with pytest.raises(dataclasses.FrozenInstanceError):
            config.model_tier = "high"


class TestDefaultStageConfigs:
    """Tests for DEFAULT_STAGE_CONFIGS constant."""

    def test_has_all_stages(self):
        """Should have configuration for all stages."""
        assert Stage.CLARIFY in DEFAULT_STAGE_CONFIGS
        assert Stage.RESEARCH in DEFAULT_STAGE_CONFIGS
        assert Stage.PLAN in DEFAULT_STAGE_CONFIGS
        assert Stage.REVIEW_PLAN in DEFAULT_STAGE_CONFIGS
        assert Stage.IMPLEMENT in DEFAULT_STAGE_CONFIGS

    def test_clarify_uses_low_tier(self):
        """Clarify stage should use low tier for fast HITL."""
        config = DEFAULT_STAGE_CONFIGS[Stage.CLARIFY]
        assert config.model_tier == "low"

    def test_research_uses_high_tier(self):
        """Research stage should use high tier for deep understanding."""
        config = DEFAULT_STAGE_CONFIGS[Stage.RESEARCH]
        assert config.model_tier == "high"

    def test_plan_uses_high_tier(self):
        """Plan stage should use high tier for complex reasoning."""
        config = DEFAULT_STAGE_CONFIGS[Stage.PLAN]
        assert config.model_tier == "high"

    def test_implement_uses_med_tier(self):
        """Implement stage should use med tier for code generation."""
        config = DEFAULT_STAGE_CONFIGS[Stage.IMPLEMENT]
        assert config.model_tier == "med"

    def test_all_configs_have_max_iters(self):
        """All stage configs should have max_iters > 0."""
        for stage, config in DEFAULT_STAGE_CONFIGS.items():
            assert config.max_iters > 0, f"{stage} has invalid max_iters"

    def test_all_configs_have_descriptions(self):
        """All default configs should have descriptions."""
        for stage, config in DEFAULT_STAGE_CONFIGS.items():
            assert config.description, f"{stage} missing description"

    @pytest.mark.parametrize(
        "stage,expected_iters",
        [
            (Stage.CLARIFY, 5),
            (Stage.RESEARCH, 3),
            (Stage.PLAN, 3),
            (Stage.REVIEW_PLAN, 3),
            (Stage.IMPLEMENT, 5),
        ],
    )
    def test_default_max_iters(self, stage: Stage, expected_iters: int):
        """Each stage should have appropriate max_iters."""
        assert DEFAULT_STAGE_CONFIGS[stage].max_iters == expected_iters
