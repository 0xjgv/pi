"""Question quality metrics for AskUserQuestion evaluation.

Provides DSPy-compatible metrics that assess:
- Question clarity and specificity
- Context appropriateness
- User experience quality
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import dspy

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# DSPy Signatures for LLM-as-Judge
# -----------------------------------------------------------------------------


class QuestionSemanticAssess(dspy.Signature):
    """Assess semantic quality of a question posed to a user."""

    question: str = dspy.InputField(desc="The question asked to the user")
    context: str = dspy.InputField(desc="Context in which question was asked")
    clarity: int = dspy.OutputField(desc="1-5: clear, unambiguous wording")
    specificity: int = dspy.OutputField(
        desc="1-5: specific enough to get useful answer"
    )
    actionability: int = dspy.OutputField(desc="1-5: user can take action to answer")
    reasoning: str = dspy.OutputField(desc="Brief justification for scores")


# -----------------------------------------------------------------------------
# Structural Checks (Fast, No LLM)
# -----------------------------------------------------------------------------


def check_question_structure(question: str) -> Mapping[str, bool]:
    """Run fast structural checks on question content.

    Args:
        question: The question text

    Returns:
        Dictionary of check names to pass/fail status
    """
    question_lower = question.lower().strip()

    return {
        "ends_with_question_mark": question.strip().endswith("?"),
        "reasonable_length": 10 <= len(question) <= 500,
        "not_empty": bool(question.strip()),
        "contains_question_word": any(
            word in question_lower
            for word in [
                "what",
                "which",
                "how",
                "where",
                "when",
                "why",
                "do",
                "can",
                "should",
                "would",
            ]
        ),
        "not_placeholder": "[" not in question and "]" not in question,
    }


def question_structural_score(question: str) -> tuple[float, list[str]]:
    """Calculate structural score and collect issues.

    Args:
        question: The question text

    Returns:
        Tuple of (score 0-1, list of issues)
    """
    checks = check_question_structure(question)
    issues = []

    for check_name, passed in checks.items():
        if not passed:
            readable_name = check_name.replace("_", " ")
            issues.append(f"Issue: {readable_name}")

    score = sum(checks.values()) / len(checks) if checks else 0.0
    return score, issues


# -----------------------------------------------------------------------------
# Semantic Assessment (LLM Judge)
# -----------------------------------------------------------------------------


def question_semantic_score(
    question: str,
    context: str,
    *,
    assessor: dspy.Module | None = None,
) -> tuple[float, list[str]]:
    """Calculate semantic quality score using LLM judge.

    Args:
        question: The question text
        context: Context in which question was asked
        assessor: Optional pre-configured assessor module

    Returns:
        Tuple of (score 0-1, list of issues)
    """
    if assessor is None:
        assessor = dspy.ChainOfThought(QuestionSemanticAssess)

    result = assessor(question=question, context=context)
    issues = []

    # Extract scores (handle both int and string outputs)
    try:
        clarity = int(result.clarity)
        specificity = int(result.specificity)
        actionability = int(result.actionability)
    except (ValueError, TypeError):
        logger.warning("Non-numeric semantic scores, defaulting to 3")
        clarity = specificity = actionability = 3

    # Collect issues for low scores
    if clarity < 3:
        issues.append(f"Low clarity ({clarity}/5): {result.reasoning[:100]}")
    if specificity < 3:
        issues.append(f"Low specificity ({specificity}/5): too vague")
    if actionability < 3:
        issues.append(
            f"Low actionability ({actionability}/5): user can't easily respond"
        )

    score = (clarity + specificity + actionability) / 15.0
    return score, issues


# -----------------------------------------------------------------------------
# Composite Metric (GEPA-Compatible)
# -----------------------------------------------------------------------------


def question_quality_metric(
    example: dspy.Example,
    pred: dspy.Prediction,
    trace: object = None,
    *,
    structural_weight: float = 0.3,
    semantic_weight: float = 0.7,
    threshold: float = 0.7,
) -> float | tuple[bool, list[str]]:
    """GEPA-compatible question quality metric.

    Combines structural and semantic assessment.

    Args:
        example: DSPy example with 'context' field
        pred: DSPy prediction with 'question' field
        trace: Trace object (present during optimization, None during evaluation)
        structural_weight: Weight for structural score (default 0.3)
        semantic_weight: Weight for semantic score (default 0.7)
        threshold: Pass/fail threshold for optimization (default 0.7)

    Returns:
        During evaluation: float score 0-1
        During optimization: tuple of (bool pass/fail, list of issues)
    """
    question = getattr(pred, "question", "") or ""
    context = getattr(example, "context", "") or "General workflow assistance"

    # Handle empty questions
    if not question.strip():
        issues = ["Question is empty"]
        if trace is not None:
            return False, issues
        return 0.0

    # Calculate structural score
    struct_score, struct_issues = question_structural_score(question)

    # Calculate semantic score
    sem_score, sem_issues = question_semantic_score(question, context)

    # Combine scores
    composite = (structural_weight * struct_score) + (semantic_weight * sem_score)
    all_issues = struct_issues + sem_issues

    if trace is not None:
        return composite >= threshold, all_issues

    return composite


# -----------------------------------------------------------------------------
# Reward Functions
# -----------------------------------------------------------------------------


def question_structural_reward(_args: dict, pred: dspy.Prediction) -> float:
    """Fast structural validation reward function.

    Args:
        _args: Input arguments (unused)
        pred: Prediction containing question

    Returns:
        Score 0-1 based on structural checks
    """
    question = getattr(pred, "question", "") or ""
    score, _ = question_structural_score(question)
    return score


def question_composite_reward(args: dict, pred: dspy.Prediction) -> float:
    """Full composite reward function.

    Args:
        args: Input arguments with 'context' key
        pred: Prediction containing question

    Returns:
        Score 0-1 based on structural + semantic assessment
    """
    context = args.get("context", "General workflow assistance")
    example = dspy.Example(context=context)
    result = question_quality_metric(example, pred, trace=None)
    return float(result) if isinstance(result, (int, float)) else 0.0
