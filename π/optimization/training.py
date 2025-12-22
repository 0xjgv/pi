"""Training data utilities for GEPA optimization.

Loads existing plans from the filesystem as DSPy examples for
training optimizers like GEPA, BootstrapFewShot, and MIPROv2.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import dspy

logger = logging.getLogger(__name__)

# Default directory for plan documents
DEFAULT_PLANS_DIR = Path("thoughts/shared/plans")


def extract_objective_from_plan(content: str, filename: str) -> str:
    """Extract objective from plan content or filename.

    Tries multiple strategies:
    1. First H1 header in the document
    2. Overview section content
    3. Filename parsing (removing date prefix)

    Args:
        content: Plan markdown content
        filename: Plan filename (e.g., "2024-01-15-ENG-123-add-auth.md")

    Returns:
        Extracted objective string
    """
    # Strategy 1: First H1 header
    h1_match = re.search(
        r"^#\s+(.+?)(?:\s+Implementation Plan)?$", content, re.MULTILINE
    )
    if h1_match:
        return h1_match.group(1).strip()

    # Strategy 2: Overview section
    overview_match = re.search(
        r"##\s+Overview\s*\n+(.+?)(?:\n\n|\n##)", content, re.DOTALL
    )
    if overview_match:
        overview = overview_match.group(1).strip()
        # Take first sentence
        first_sentence = overview.split(".")[0]
        if len(first_sentence) > 10:
            return first_sentence.strip()

    # Strategy 3: Parse filename
    # Remove common prefixes: YYYY-MM-DD, ENG-XXX, etc.
    name = Path(filename).stem
    # Remove date prefix
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", name)
    # Remove ticket prefix
    name = re.sub(r"^[A-Z]+-\d+-?", "", name)
    # Convert kebab-case to spaces
    name = name.replace("-", " ").replace("_", " ")

    return name.strip().capitalize() if name else "Unknown objective"


def load_plan_examples(
    plans_dir: Path | str = DEFAULT_PLANS_DIR,
    *,
    min_length: int = 200,
    max_examples: int | None = None,
) -> list[dspy.Example]:
    """Load existing plans as DSPy training examples.

    Scans the plans directory for markdown files and converts them
    into DSPy Examples suitable for optimizer training.

    Args:
        plans_dir: Directory containing plan markdown files
        min_length: Minimum plan content length to include
        max_examples: Maximum number of examples to load (None for all)

    Returns:
        List of DSPy Examples with 'objective' as input and
        'plan_summary' as the expected output
    """
    plans_path = Path(plans_dir)
    if not plans_path.exists():
        logger.warning(f"Plans directory not found: {plans_path}")
        return []

    examples = []
    plan_files = sorted(plans_path.glob("*.md"), reverse=True)  # Most recent first

    for plan_file in plan_files:
        if max_examples and len(examples) >= max_examples:
            break

        try:
            content = plan_file.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read {plan_file}: {e}")
            continue

        # Skip too-short plans
        if len(content) < min_length:
            logger.debug(f"Skipping {plan_file.name}: too short ({len(content)} chars)")
            continue

        objective = extract_objective_from_plan(content, plan_file.name)

        example = dspy.Example(
            objective=objective,
            plan_summary=content,
        ).with_inputs("objective")

        examples.append(example)
        logger.debug(f"Loaded example from {plan_file.name}: '{objective[:50]}...'")

    logger.info(f"Loaded {len(examples)} plan examples from {plans_path}")
    return examples


def split_train_val(
    examples: list[dspy.Example],
    val_ratio: float = 0.2,
) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """Split examples into training and validation sets.

    Args:
        examples: List of DSPy examples
        val_ratio: Fraction to use for validation (default 0.2)

    Returns:
        Tuple of (trainset, valset)
    """
    if not examples:
        return [], []

    split_idx = max(1, int(len(examples) * (1 - val_ratio)))
    return examples[:split_idx], examples[split_idx:]


def create_synthetic_examples(
    objectives: list[str],
) -> list[dspy.Example]:
    """Create synthetic examples for bootstrapping.

    Use when you have objectives but no ground-truth plans yet.
    The optimizer will generate plan_summary during bootstrapping.

    Args:
        objectives: List of objective strings

    Returns:
        List of DSPy Examples with objectives as inputs
    """
    return [dspy.Example(objective=obj).with_inputs("objective") for obj in objectives]
