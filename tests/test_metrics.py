"""Tests for plan quality metrics."""

from unittest.mock import MagicMock, patch

import dspy
import pytest

from π.optimization import (
    check_plan_structure,
    composite_reward,
    plan_quality_metric,
    semantic_score,
    structural_reward,
    structural_score,
)


# =============================================================================
# Test Data
# =============================================================================

GOOD_PLAN = """# Add Authentication Implementation Plan

## Overview
Implement user authentication with JWT tokens for secure API access.
This plan covers the complete authentication flow including login,
token refresh, and logout functionality.

## Phase 1: Setup
**File**: `π/auth.py`
Add authentication module with JWT token generation and validation.
Include helper functions for password hashing and verification.

**File**: `π/models/user.py`
Add User model with email, password_hash, and created_at fields.

## Phase 2: Integration
**File**: `π/cli.py`
Integrate auth checks into CLI commands.
Add login and logout commands.

**File**: `π/middleware.py`
Add authentication middleware for protected routes.

## Success Criteria
- [ ] Tests pass for all auth functions
- [ ] Build succeeds without errors
- [ ] Login flow works end-to-end
- [ ] Token refresh works correctly

## What We're NOT Doing
- OAuth integration (future work)
- Social login providers
- Multi-factor authentication
- Password reset via email
"""

MINIMAL_PLAN = "Add feature X"

PARTIAL_PLAN = """# Feature Plan

## Phase 1: Implementation
Add the feature.

## Success Criteria
- [ ] Feature works
"""


# =============================================================================
# Structural Checks Tests
# =============================================================================


class TestCheckPlanStructure:
    """Tests for check_plan_structure function."""

    def test_good_plan_passes_all_checks(self):
        """Good plan should pass all structural checks."""
        checks = check_plan_structure(GOOD_PLAN)

        assert checks["phase_structure"] is True
        assert checks["file_references"] is True
        assert checks["success_criteria"] is True
        assert checks["scope_boundaries"] is True
        assert checks["substantial_length"] is True

    def test_minimal_plan_fails_all_checks(self):
        """Minimal plan should fail all checks."""
        checks = check_plan_structure(MINIMAL_PLAN)

        assert checks["phase_structure"] is False
        assert checks["file_references"] is False
        assert checks["success_criteria"] is False
        assert checks["scope_boundaries"] is False
        assert checks["substantial_length"] is False

    def test_partial_plan_passes_some_checks(self):
        """Partial plan should pass some checks."""
        checks = check_plan_structure(PARTIAL_PLAN)

        assert checks["phase_structure"] is True
        assert checks["success_criteria"] is True
        assert checks["file_references"] is False
        assert checks["scope_boundaries"] is False


class TestStructuralScore:
    """Tests for structural_score function."""

    def test_good_plan_high_score(self):
        """Good plan should have high structural score."""
        score, issues = structural_score(GOOD_PLAN)

        assert score == 1.0
        assert issues == []

    def test_minimal_plan_low_score(self):
        """Minimal plan should have low structural score."""
        score, issues = structural_score(MINIMAL_PLAN)

        assert score == 0.0
        assert len(issues) == 5

    def test_partial_plan_medium_score(self):
        """Partial plan should have medium structural score."""
        score, issues = structural_score(PARTIAL_PLAN)

        assert 0.0 < score < 1.0
        assert len(issues) > 0


# =============================================================================
# Semantic Score Tests
# =============================================================================


class TestSemanticScore:
    """Tests for semantic_score function."""

    def test_with_mock_assessor(self):
        """Test semantic scoring with mocked LLM judge."""
        # Create mock assessor
        mock_assessor = MagicMock()
        mock_assessor.return_value = MagicMock(
            completeness=4,
            specificity=5,
            reasoning="Well structured plan",
        )

        score, issues = semantic_score(
            GOOD_PLAN,
            "Add authentication",
            assessor=mock_assessor,
        )

        assert score == 0.9  # (4 + 5) / 10
        assert issues == []
        mock_assessor.assert_called_once()

    def test_low_completeness_generates_issue(self):
        """Low completeness score should generate issue."""
        mock_assessor = MagicMock()
        mock_assessor.return_value = MagicMock(
            completeness=2,
            specificity=4,
            reasoning="Missing requirements",
        )

        score, issues = semantic_score(
            PARTIAL_PLAN,
            "Add feature",
            assessor=mock_assessor,
        )

        assert score == 0.6  # (2 + 4) / 10
        assert len(issues) == 1
        assert "Low completeness" in issues[0]

    def test_low_specificity_generates_issue(self):
        """Low specificity score should generate issue."""
        mock_assessor = MagicMock()
        mock_assessor.return_value = MagicMock(
            completeness=4,
            specificity=1,
            reasoning="Too vague",
        )

        score, issues = semantic_score(
            PARTIAL_PLAN,
            "Add feature",
            assessor=mock_assessor,
        )

        assert score == 0.5  # (4 + 1) / 10
        assert len(issues) == 1
        assert "Low specificity" in issues[0]


# =============================================================================
# Plan Quality Metric Tests
# =============================================================================


class TestPlanQualityMetric:
    """Tests for plan_quality_metric function."""

    @pytest.fixture
    def mock_semantic_assessor(self):
        """Fixture to mock the semantic assessor."""
        with patch("π.optimization.metrics.dspy.ChainOfThought") as mock_cot:
            mock_assessor = MagicMock()
            mock_assessor.return_value = MagicMock(
                completeness=4,
                specificity=4,
                reasoning="Good plan",
            )
            mock_cot.return_value = mock_assessor
            yield mock_assessor

    def test_evaluation_mode_returns_float(self, mock_semantic_assessor):
        """In evaluation mode (trace=None), should return float."""
        _ = mock_semantic_assessor  # Used via patch fixture
        example = dspy.Example(objective="Add auth")
        pred = MagicMock()
        pred.plan_summary = GOOD_PLAN

        result = plan_quality_metric(example, pred, trace=None)

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_optimization_mode_returns_tuple(self, mock_semantic_assessor):
        """In optimization mode (trace not None), should return tuple."""
        _ = mock_semantic_assessor  # Used via patch fixture
        example = dspy.Example(objective="Add auth")
        pred = MagicMock()
        pred.plan_summary = GOOD_PLAN

        result = plan_quality_metric(example, pred, trace=object())

        assert isinstance(result, tuple)
        passed, issues = result
        assert isinstance(passed, bool)
        assert isinstance(issues, list)

    def test_empty_plan_returns_zero(self):
        """Empty plan should return zero score."""
        example = dspy.Example(objective="Add auth")
        pred = MagicMock()
        pred.plan_summary = ""

        result = plan_quality_metric(example, pred, trace=None)

        assert result == 0.0

    def test_empty_plan_fails_optimization(self):
        """Empty plan should fail in optimization mode."""
        example = dspy.Example(objective="Add auth")
        pred = MagicMock()
        pred.plan_summary = ""

        result = plan_quality_metric(example, pred, trace=object())
        assert isinstance(result, tuple)
        passed, issues = result

        assert passed is False
        assert "empty" in issues[0].lower()


# =============================================================================
# Reward Functions Tests
# =============================================================================


class TestStructuralReward:
    """Tests for structural_reward function."""

    def test_returns_float(self):
        """Structural reward should return float score."""
        pred = MagicMock()
        pred.plan_summary = GOOD_PLAN

        result = structural_reward({}, pred)

        assert isinstance(result, float)
        assert result == 1.0

    def test_handles_missing_plan_summary(self):
        """Should handle prediction without plan_summary."""
        pred = MagicMock(spec=[])  # No attributes

        result = structural_reward({}, pred)

        assert result == 0.0


class TestCompositeReward:
    """Tests for composite_reward function."""

    def test_uses_objective_from_args(self):
        """Should extract objective from args dict."""
        with patch("π.optimization.metrics.plan_quality_metric") as mock_metric:
            mock_metric.return_value = 0.8
            pred = MagicMock()
            pred.plan_summary = GOOD_PLAN

            result = composite_reward({"objective": "Add auth"}, pred)

            assert result == 0.8
            # Verify example was created with objective
            call_args = mock_metric.call_args
            example = call_args[0][0]
            assert example.objective == "Add auth"


# =============================================================================
# Integration Tests
# =============================================================================


class TestMetricsIntegration:
    """Integration tests combining multiple metric components."""

    def test_structural_and_semantic_combined(self):
        """Test that structural and semantic scores combine correctly."""
        with patch("π.optimization.metrics.dspy.ChainOfThought") as mock_cot:
            mock_assessor = MagicMock()
            # Perfect semantic scores
            mock_assessor.return_value = MagicMock(
                completeness=5,
                specificity=5,
                reasoning="Perfect plan",
            )
            mock_cot.return_value = mock_assessor

            example = dspy.Example(objective="Add auth")
            pred = MagicMock()
            pred.plan_summary = GOOD_PLAN

            # With default weights (0.4 structural, 0.6 semantic)
            # structural = 1.0, semantic = 1.0
            # composite = 0.4 * 1.0 + 0.6 * 1.0 = 1.0
            result = plan_quality_metric(example, pred, trace=None)

            assert result == pytest.approx(1.0, abs=0.01)

    def test_threshold_boundary(self):
        """Test optimization pass/fail at threshold boundary."""
        with patch("π.optimization.metrics.dspy.ChainOfThought") as mock_cot:
            mock_assessor = MagicMock()
            # Scores that put us right at threshold
            mock_assessor.return_value = MagicMock(
                completeness=3,
                specificity=3,
                reasoning="Okay plan",
            )
            mock_cot.return_value = mock_assessor

            example = dspy.Example(objective="Add auth")
            pred = MagicMock()
            pred.plan_summary = GOOD_PLAN

            # structural = 1.0, semantic = 0.6
            # composite = 0.4 * 1.0 + 0.6 * 0.6 = 0.76
            # threshold = 0.75, so should pass
            result = plan_quality_metric(example, pred, trace=object())
            assert isinstance(result, tuple)
            passed, _ = result

            assert passed is True
