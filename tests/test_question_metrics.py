"""Tests for question quality metrics."""

from unittest.mock import MagicMock, patch

import dspy
import pytest

from π.optimization import (
    check_question_structure,
    question_composite_reward,
    question_quality_metric,
    question_semantic_score,
    question_structural_reward,
    question_structural_score,
)


# =============================================================================
# Test Data
# =============================================================================

GOOD_QUESTION = "What authentication method should we use for the API endpoints?"

MINIMAL_QUESTION = "thing?"

BAD_QUESTION = ""

PLACEHOLDER_QUESTION = "[No response provided]"


# =============================================================================
# Structural Checks Tests
# =============================================================================


class TestCheckQuestionStructure:
    """Tests for check_question_structure function."""

    def test_good_question_passes_all_checks(self):
        """Good question should pass all structural checks."""
        checks = check_question_structure(GOOD_QUESTION)

        assert checks["ends_with_question_mark"] is True
        assert checks["reasonable_length"] is True
        assert checks["not_empty"] is True
        assert checks["contains_question_word"] is True
        assert checks["not_placeholder"] is True

    def test_empty_question_fails_checks(self):
        """Empty question should fail key checks."""
        checks = check_question_structure(BAD_QUESTION)

        assert checks["not_empty"] is False
        assert checks["reasonable_length"] is False

    def test_placeholder_question_detected(self):
        """Placeholder question should fail not_placeholder check."""
        checks = check_question_structure(PLACEHOLDER_QUESTION)

        assert checks["not_placeholder"] is False


class TestQuestionStructuralScore:
    """Tests for question_structural_score function."""

    def test_good_question_high_score(self):
        """Good question should have high structural score."""
        score, issues = question_structural_score(GOOD_QUESTION)

        assert score == 1.0
        assert issues == []

    def test_empty_question_low_score(self):
        """Empty question should have low structural score."""
        score, issues = question_structural_score(BAD_QUESTION)

        assert score < 0.5
        assert len(issues) > 0


# =============================================================================
# Semantic Score Tests
# =============================================================================


class TestQuestionSemanticScore:
    """Tests for question_semantic_score function."""

    def test_with_mock_assessor(self):
        """Test semantic scoring with mocked LLM judge."""
        mock_assessor = MagicMock()
        mock_assessor.return_value = MagicMock(
            clarity=5,
            specificity=4,
            actionability=5,
            reasoning="Clear, specific question",
        )

        score, issues = question_semantic_score(
            GOOD_QUESTION,
            "Planning API implementation",
            assessor=mock_assessor,
        )

        assert score == pytest.approx(14 / 15, abs=0.01)
        assert issues == []
        mock_assessor.assert_called_once()

    def test_low_clarity_generates_issue(self):
        """Low clarity score should generate issue."""
        mock_assessor = MagicMock()
        mock_assessor.return_value = MagicMock(
            clarity=2,
            specificity=4,
            actionability=4,
            reasoning="Unclear wording",
        )

        score, issues = question_semantic_score(
            MINIMAL_QUESTION,
            "Unknown context",
            assessor=mock_assessor,
        )

        assert len(issues) == 1
        assert "Low clarity" in issues[0]


# =============================================================================
# Question Quality Metric Tests
# =============================================================================


class TestQuestionQualityMetric:
    """Tests for question_quality_metric function."""

    @pytest.fixture
    def mock_semantic_assessor(self):
        """Fixture to mock the semantic assessor."""
        with patch("π.optimization.question_metrics.dspy.ChainOfThought") as mock_cot:
            mock_assessor = MagicMock()
            mock_assessor.return_value = MagicMock(
                clarity=4,
                specificity=4,
                actionability=4,
                reasoning="Good question",
            )
            mock_cot.return_value = mock_assessor
            yield mock_assessor

    def test_evaluation_mode_returns_float(self, mock_semantic_assessor):
        """In evaluation mode (trace=None), should return float."""
        _ = mock_semantic_assessor
        example = dspy.Example(context="API planning")
        pred = MagicMock()
        pred.question = GOOD_QUESTION

        result = question_quality_metric(example, pred, trace=None)

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_optimization_mode_returns_tuple(self, mock_semantic_assessor):
        """In optimization mode (trace not None), should return tuple."""
        _ = mock_semantic_assessor
        example = dspy.Example(context="API planning")
        pred = MagicMock()
        pred.question = GOOD_QUESTION

        result = question_quality_metric(example, pred, trace=object())

        assert isinstance(result, tuple)
        passed, issues = result
        assert isinstance(passed, bool)
        assert isinstance(issues, list)

    def test_empty_question_returns_zero(self):
        """Empty question should return zero score."""
        example = dspy.Example(context="Any context")
        pred = MagicMock()
        pred.question = ""

        result = question_quality_metric(example, pred, trace=None)

        assert result == 0.0


# =============================================================================
# Reward Functions Tests
# =============================================================================


class TestQuestionStructuralReward:
    """Tests for question_structural_reward function."""

    def test_returns_float(self):
        """Structural reward should return float score."""
        pred = MagicMock()
        pred.question = GOOD_QUESTION

        result = question_structural_reward({}, pred)

        assert isinstance(result, float)
        assert result == 1.0


class TestQuestionCompositeReward:
    """Tests for question_composite_reward function."""

    def test_uses_context_from_args(self):
        """Should extract context from args dict."""
        with patch(
            "π.optimization.question_metrics.question_quality_metric"
        ) as mock_metric:
            mock_metric.return_value = 0.85
            pred = MagicMock()
            pred.question = GOOD_QUESTION

            result = question_composite_reward({"context": "API planning"}, pred)

            assert result == 0.85
            call_args = mock_metric.call_args
            example = call_args[0][0]
            assert example.context == "API planning"
