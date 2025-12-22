"""Plan quality metrics for GEPA optimization.

Provides DSPy-compatible metrics that return (score, feedback) for
evolutionary prompt optimization via GEPA.
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


class PlanSemanticAssess(dspy.Signature):
    """Assess semantic quality of an implementation plan."""

    plan_content: str = dspy.InputField(desc="The plan markdown content")
    objective: str = dspy.InputField(desc="Original user objective")
    completeness: int = dspy.OutputField(desc="1-5: covers all requirements")
    specificity: int = dspy.OutputField(desc="1-5: concrete file paths & code")
    reasoning: str = dspy.OutputField(desc="Brief justification for scores")


# -----------------------------------------------------------------------------
# Structural Checks (Fast, No LLM)
# -----------------------------------------------------------------------------


def check_plan_structure(plan: str) -> Mapping[str, bool]:
    """Run fast structural checks on plan content.

    Args:
        plan: Plan markdown content

    Returns:
        Dictionary of check names to pass/fail status
    """
    return {
        "phase_structure": "## Phase" in plan or "### Phase" in plan,
        "file_references": "**File**:" in plan or "`π/" in plan or "path/" in plan,
        "success_criteria": "Success Criteria" in plan or "- [ ]" in plan,
        "scope_boundaries": "NOT Doing" in plan or "Out of Scope" in plan,
        "substantial_length": len(plan) > 500,
    }


def structural_score(plan: str) -> tuple[float, list[str]]:
    """Calculate structural score and collect issues.

    Args:
        plan: Plan markdown content

    Returns:
        Tuple of (score 0-1, list of issues)
    """
    checks = check_plan_structure(plan)
    issues = []

    for check_name, passed in checks.items():
        if not passed:
            readable_name = check_name.replace("_", " ")
            issues.append(f"Missing: {readable_name}")

    score = sum(checks.values()) / len(checks) if checks else 0.0
    return score, issues


# -----------------------------------------------------------------------------
# Semantic Assessment (LLM Judge)
# -----------------------------------------------------------------------------


def semantic_score(
    plan: str,
    objective: str,
    *,
    assessor: dspy.Module | None = None,
) -> tuple[float, list[str]]:
    """Calculate semantic quality score using LLM judge.

    Args:
        plan: Plan markdown content
        objective: Original user objective
        assessor: Optional pre-configured assessor module

    Returns:
        Tuple of (score 0-1, list of issues)
    """
    if assessor is None:
        assessor = dspy.ChainOfThought(PlanSemanticAssess)

    result = assessor(plan_content=plan, objective=objective)
    issues = []

    # Extract scores (handle both int and string outputs)
    try:
        completeness = int(result.completeness)
        specificity = int(result.specificity)
    except (ValueError, TypeError):
        # Fallback if LLM returns non-numeric
        logger.warning("Non-numeric semantic scores, defaulting to 3")
        completeness = 3
        specificity = 3

    # Collect issues for low scores
    if completeness < 3:
        issues.append(f"Low completeness ({completeness}/5): {result.reasoning[:100]}")
    if specificity < 3:
        issues.append(
            f"Low specificity ({specificity}/5): needs more concrete code/paths"
        )

    score = (completeness + specificity) / 10.0
    return score, issues


# -----------------------------------------------------------------------------
# Composite Metric (GEPA-Compatible)
# -----------------------------------------------------------------------------


def plan_quality_metric(
    example: dspy.Example,
    pred: dspy.Prediction,
    trace: object = None,
    *,
    structural_weight: float = 0.4,
    semantic_weight: float = 0.6,
    threshold: float = 0.75,
) -> float | tuple[bool, list[str]]:
    """GEPA-compatible plan quality metric.

    Combines structural and semantic assessment to produce a composite score.
    When called during optimization (trace is not None), returns (pass/fail, issues).
    When called during evaluation (trace is None), returns float score.

    Args:
        example: DSPy example with 'objective' field
        pred: DSPy prediction with 'plan_summary' field
        trace: Trace object (present during optimization, None during evaluation)
        structural_weight: Weight for structural score (default 0.4)
        semantic_weight: Weight for semantic score (default 0.6)
        threshold: Pass/fail threshold for optimization (default 0.75)

    Returns:
        During evaluation: float score 0-1
        During optimization: tuple of (bool pass/fail, list of issues)
    """
    # Extract plan content from prediction
    plan = getattr(pred, "plan_summary", "") or ""

    # Handle empty plans
    if not plan:
        issues = ["Plan is empty or missing plan_summary field"]
        if trace is not None:
            return False, issues
        return 0.0

    # Get objective from example
    objective = getattr(example, "objective", "") or ""

    # Calculate structural score
    struct_score, struct_issues = structural_score(plan)

    # Calculate semantic score (skip if no objective)
    if objective:
        sem_score, sem_issues = semantic_score(plan, objective)
    else:
        sem_score = 0.5  # Neutral if no objective to judge against
        sem_issues = []

    # Combine scores
    composite = (structural_weight * struct_score) + (semantic_weight * sem_score)
    all_issues = struct_issues + sem_issues

    if trace is not None:
        # Optimization mode: return (pass/fail, feedback)
        return composite >= threshold, all_issues

    # Evaluation mode: return float score
    return composite


# -----------------------------------------------------------------------------
# Reward Functions for dspy.Refine / dspy.BestOfN
# -----------------------------------------------------------------------------


def structural_reward(_args: dict, pred: dspy.Prediction) -> float:
    """Fast structural validation reward function.

    Suitable for dspy.BestOfN where speed matters.

    Args:
        args: Input arguments (unused, required by dspy.BestOfN signature)
        pred: Prediction containing plan_summary

    Returns:
        Score 0-1 based on structural checks
    """
    plan = getattr(pred, "plan_summary", "") or ""
    score, _ = structural_score(plan)
    return score


def composite_reward(args: dict, pred: dspy.Prediction) -> float:
    """Full composite reward function.

    Suitable for dspy.Refine where quality matters more than speed.

    Args:
        args: Input arguments with 'objective' key
        pred: Prediction containing plan_summary

    Returns:
        Score 0-1 based on structural + semantic assessment
    """
    objective = args.get("objective", "")
    example = dspy.Example(objective=objective)
    result = plan_quality_metric(example, pred, trace=None)
    # trace=None always returns float, but cast for type checker
    return float(result) if isinstance(result, (int, float)) else 0.0
