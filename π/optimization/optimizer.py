"""GEPA optimization for plan quality.

Provides utilities to optimize the RPIWorkflow using GEPA
(Genetic-Pareto / Reflective Prompt Evolution) optimizer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import dspy

if TYPE_CHECKING:
    from collections.abc import Callable

from π.optimization.metrics import plan_quality_metric
from π.optimization.training import (
    DEFAULT_PLANS_DIR,
    load_plan_examples,
    split_train_val,
)
from π.workflow import RPIWorkflow

logger = logging.getLogger(__name__)

# Default path for saving optimized workflow
DEFAULT_OPTIMIZED_PATH = Path("π/optimized_workflow.json")


def optimize_workflow(
    *,
    plans_dir: Path | str = DEFAULT_PLANS_DIR,
    output_path: Path | str = DEFAULT_OPTIMIZED_PATH,
    num_generations: int = 10,
    _population_size: int = 20,  # Reserved for future GEPA versions
    min_examples: int = 5,
    metric: Callable | None = None,
    _verbose: bool = True,  # Reserved for future GEPA versions
) -> dspy.Module:
    """Optimize RPIWorkflow using GEPA.

    Loads existing plans as training data and runs GEPA optimization
    to improve plan generation quality.

    Args:
        plans_dir: Directory containing plan markdown files
        output_path: Path to save optimized workflow JSON
        num_generations: Number of evolution iterations
        population_size: Size of candidate pool per generation
        min_examples: Minimum examples required to run optimization
        metric: Custom metric function (default: plan_quality_metric)
        verbose: Whether to print progress

    Returns:
        Optimized RPIWorkflow instance

    Raises:
        ValueError: If fewer than min_examples plans are available
    """
    # Load training data
    examples = load_plan_examples(plans_dir)

    if len(examples) < min_examples:
        msg = (
            f"GEPA needs at least {min_examples} examples, "
            f"found {len(examples)} in {plans_dir}"
        )
        raise ValueError(msg)

    # Split into train/val
    trainset, valset = split_train_val(examples, val_ratio=0.2)
    logger.info(
        f"Training: {len(trainset)} examples, Validation: {len(valset)} examples"
    )

    # Configure GEPA optimizer
    # Note: GEPA parameters may vary by dspy version
    try:
        from dspy.teleprompt import GEPA
    except ImportError as e:
        msg = "GEPA optimizer not available. Ensure dspy>=3.0.4 is installed."
        raise ImportError(msg) from e

    # Build GEPA with metric
    # Note: GEPA API may vary by dspy version, we use the metric parameter
    # which is standard across versions
    _ = num_generations  # Reserved for future use when GEPA supports it
    gepa = GEPA(metric=metric or plan_quality_metric)

    # Create base workflow
    base_workflow = RPIWorkflow()

    # Run optimization
    logger.info(f"Starting GEPA optimization ({num_generations} generations)...")
    optimized = gepa.compile(student=base_workflow, trainset=trainset)

    # Save optimized workflow
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    optimized.save(str(output_path))
    logger.info(f"Saved optimized workflow to {output_path}")

    return optimized


def evaluate_workflow(
    workflow: RPIWorkflow,
    *,
    plans_dir: Path | str = DEFAULT_PLANS_DIR,
    metric: Callable | None = None,
    num_threads: int = 4,
) -> float:
    """Evaluate workflow quality on existing plans.

    Args:
        workflow: RPIWorkflow instance to evaluate
        plans_dir: Directory containing plan markdown files
        metric: Metric function (default: plan_quality_metric)
        num_threads: Number of parallel evaluation threads

    Returns:
        Average score across all examples
    """
    examples = load_plan_examples(plans_dir)

    if not examples:
        logger.warning(f"No examples found in {plans_dir}")
        return 0.0

    evaluator = dspy.Evaluate(
        devset=examples,
        metric=metric or plan_quality_metric,
        num_threads=num_threads,
        display_progress=True,
    )

    result = evaluator(workflow)
    return result.score


def compare_workflows(
    base: RPIWorkflow,
    optimized: RPIWorkflow,
    *,
    plans_dir: Path | str = DEFAULT_PLANS_DIR,
) -> dict[str, float]:
    """Compare base vs optimized workflow performance.

    Args:
        base: Unoptimized RPIWorkflow
        optimized: GEPA-optimized RPIWorkflow
        plans_dir: Directory containing plan markdown files

    Returns:
        Dictionary with 'base_score', 'optimized_score', 'improvement'
    """
    base_score = evaluate_workflow(base, plans_dir=plans_dir)
    optimized_score = evaluate_workflow(optimized, plans_dir=plans_dir)

    return {
        "base_score": base_score,
        "optimized_score": optimized_score,
        "improvement": optimized_score - base_score,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Optimize RPIWorkflow with GEPA")
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=DEFAULT_PLANS_DIR,
        help="Directory containing plan markdown files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OPTIMIZED_PATH,
        help="Path to save optimized workflow",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=10,
        help="Number of GEPA generations",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=20,
        help="GEPA population size",
    )
    parser.add_argument(
        "--min-examples",
        type=int,
        default=5,
        help="Minimum examples required",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only evaluate existing workflow, don't optimize",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.evaluate_only:
        # Load and evaluate existing optimized workflow
        if args.output.exists():
            workflow = RPIWorkflow.load_optimized(path=args.output)
            score = evaluate_workflow(workflow, plans_dir=args.plans_dir)
            print(f"Evaluation score: {score:.2%}")
        else:
            print(f"No optimized workflow found at {args.output}")
    else:
        # Run optimization
        optimize_workflow(
            plans_dir=args.plans_dir,
            output_path=args.output,
            num_generations=args.generations,
            population_size=args.population,
            min_examples=args.min_examples,
            verbose=args.verbose,
        )
