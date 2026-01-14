"""Tests for π.config.stages module."""

from π.config import MAX_ITERS, STAGE_TIERS, WorkflowStage
from π.core.enums import Tier


class TestWorkflowStage:
    """Tests for WorkflowStage enum."""

    def test_has_all_workflow_stages(self):
        """Should define all workflow stages."""
        assert WorkflowStage.RESEARCH == "research"
        assert WorkflowStage.DESIGN == "design"
        assert WorkflowStage.EXECUTE == "execute"

    def test_stage_count(self):
        """Should have exactly 3 stages."""
        assert len(WorkflowStage) == 3

    def test_stages_are_strings(self):
        """Stage values should be strings for serialization."""
        for stage in WorkflowStage:
            assert isinstance(stage.value, str)


class TestStageTiers:
    """Tests for STAGE_TIERS configuration."""

    def test_has_all_stages(self):
        """Should have configuration for all workflow stages."""
        assert WorkflowStage.RESEARCH in STAGE_TIERS
        assert WorkflowStage.DESIGN in STAGE_TIERS
        assert WorkflowStage.EXECUTE in STAGE_TIERS

    def test_research_uses_high_tier(self):
        """Research stage should use high tier for deep understanding."""
        assert STAGE_TIERS[WorkflowStage.RESEARCH] == Tier.HIGH

    def test_design_uses_high_tier(self):
        """Design stage should use high tier for complex reasoning."""
        assert STAGE_TIERS[WorkflowStage.DESIGN] == Tier.HIGH

    def test_execute_uses_high_tier(self):
        """Execute stage should use high tier for thorough implementation."""
        assert STAGE_TIERS[WorkflowStage.EXECUTE] == Tier.HIGH

    def test_all_tiers_are_valid(self):
        """All tier values should be valid Tier enum members."""
        for stage, tier in STAGE_TIERS.items():
            assert isinstance(tier, Tier), f"{stage} has invalid tier: {tier}"


class TestMaxIters:
    """Tests for MAX_ITERS constant."""

    def test_max_iters_is_positive(self):
        """MAX_ITERS should be a positive integer."""
        assert MAX_ITERS > 0

    def test_max_iters_value(self):
        """MAX_ITERS should be 5."""
        assert MAX_ITERS == 5
