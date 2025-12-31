"""Tests for π.config.stages module."""

from π.config import MAX_ITERS, STAGE_TIERS, Stage


class TestStage:
    """Tests for Stage enum."""

    def test_has_all_workflow_stages(self):
        """Should define all four workflow stages."""
        assert Stage.RESEARCH_CODEBASE == "research_codebase"
        assert Stage.PLAN == "plan"
        assert Stage.REVIEW_PLAN == "review_plan"
        assert Stage.ITERATE_PLAN == "iterate_plan"

    def test_stage_count(self):
        """Should have exactly 4 stages."""
        assert len(Stage) == 4

    def test_stages_are_strings(self):
        """Stage values should be strings for serialization."""
        for stage in Stage:
            assert isinstance(stage.value, str)


class TestStageTiers:
    """Tests for STAGE_TIERS configuration."""

    def test_has_active_stages(self):
        """Should have configuration for active workflow stages."""
        # Only RESEARCH, PLAN, REVIEW_PLAN are currently active in workflow
        assert Stage.RESEARCH_CODEBASE in STAGE_TIERS
        assert Stage.PLAN in STAGE_TIERS
        assert Stage.REVIEW_PLAN in STAGE_TIERS

    def test_research_uses_high_tier(self):
        """Research stage should use high tier for deep understanding."""
        assert STAGE_TIERS[Stage.RESEARCH_CODEBASE] == "high"

    def test_plan_uses_high_tier(self):
        """Plan stage should use high tier for complex reasoning."""
        assert STAGE_TIERS[Stage.PLAN] == "high"

    def test_review_plan_uses_high_tier(self):
        """Review plan stage should use high tier for thorough review."""
        assert STAGE_TIERS[Stage.REVIEW_PLAN] == "high"

    def test_all_tiers_are_valid(self):
        """All tier values should be valid tier strings."""
        valid_tiers = {"low", "med", "high"}
        for stage, tier in STAGE_TIERS.items():
            assert tier in valid_tiers, f"{stage} has invalid tier: {tier}"


class TestMaxIters:
    """Tests for MAX_ITERS constant."""

    def test_max_iters_is_positive(self):
        """MAX_ITERS should be a positive integer."""
        assert MAX_ITERS > 0

    def test_max_iters_value(self):
        """MAX_ITERS should be 5."""
        assert MAX_ITERS == 5
