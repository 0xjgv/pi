"""Staged workflow tools with type-safe results.

These functions wrap the existing decorated tools from tools.py,
adding type-safe document validation and bundling related stages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from π.workflow.context import get_extracted_path
from π.workflow.tools import commit_changes as _commit_changes
from π.workflow.tools import create_plan as _create_plan
from π.workflow.tools import implement_plan as _implement_plan
from π.workflow.tools import iterate_plan as _iterate_plan
from π.workflow.tools import research_codebase as _research_codebase
from π.workflow.tools import review_plan as _review_plan
from π.workflow.types import (
    DesignResult,
    ExecuteResult,
    PlanDocPath,
    ResearchDocPath,
    ResearchResult,
)

logger = logging.getLogger(__name__)

# Triage signals - distinct from bridge.py's doc completion signals
# These detect if the TASK itself is already done (not just doc extraction)
_TRIAGE_SIGNALS = (
    "already implemented",
    "already exists",
    "no changes needed",
    "nothing to do",
    "feature exists",
)


def _needs_implementation(result: str) -> bool:
    """Check if research indicates implementation is needed.

    Note: This is distinct from bridge.py's _result_indicates_completion()
    which checks if an agent finished without creating a new document.
    This function checks if the TASK itself needs work.
    """
    result_lower = result.lower()
    return not any(signal in result_lower for signal in _TRIAGE_SIGNALS)


def stage_research(*, objective: str) -> ResearchResult:
    """Research stage: triage gate.

    Executes research via the decorated tool and determines if implementation is needed.

    Args:
        objective: The objective to research.

    Returns:
        ResearchResult with validated ResearchDocPath and needs_implementation flag.

    Raises:
        ValueError: If research did not produce a valid document.
    """
    # Call the decorated tool (preserves session mgmt, timing, error handling)
    result = _research_codebase(query=objective)

    # Get validated path from context (stored by @workflow_tool decorator)
    raw_path = get_extracted_path("research")

    if not raw_path:
        raise ValueError(
            "Research did not produce a document at thoughts/shared/research/. "
            "Agent should output 'Document saved at: <path>'."
        )

    # Validate via Pydantic (adds type discrimination)
    research_doc = ResearchDocPath(path=raw_path)

    # Determine if implementation needed
    needs_impl = _needs_implementation(result)

    logger.info(
        "Research complete: needs_implementation=%s, doc=%s",
        needs_impl,
        research_doc.path,
    )

    return ResearchResult(
        research_doc=research_doc,
        summary=result[:500],
        needs_implementation=needs_impl,
        reason=None if needs_impl else "Task already implemented or not needed",
    )


def stage_design(
    *,
    research_doc: ResearchDocPath,
    objective: str,
) -> DesignResult:
    """Design stage: plan + review + iterate.

    Bundles plan creation, review, and iteration using the decorated tools.

    Args:
        research_doc: Validated ResearchDocPath from research stage.
        objective: The original objective.

    Returns:
        DesignResult with validated PlanDocPath.

    Raises:
        ValueError: If design did not produce a valid plan document.
    """
    # Step 1: Create plan (uses decorated tool)
    logger.info("Design step 1/3: Creating plan")
    _create_plan(
        research_document_path=Path(research_doc.path),
        query=objective,
    )

    # Get plan path from context
    plan_path = get_extracted_path("plan")
    if not plan_path:
        raise ValueError(
            "Plan stage did not produce a document at thoughts/shared/plans/."
        )

    # Step 2: Review plan
    logger.info("Design step 2/3: Reviewing plan")
    review_result = _review_plan(
        plan_document_path=Path(plan_path),
        query="review the plan for completeness and accuracy",
    )

    # Step 3: Iterate on plan based on review feedback
    logger.info("Design step 3/3: Iterating plan")
    iterate_result = _iterate_plan(
        plan_document_path=Path(plan_path),
        review_feedback=review_result[:1000],
    )

    # Validate via Pydantic (adds type discrimination)
    plan_doc = PlanDocPath(path=plan_path)

    logger.info("Design complete: plan=%s", plan_doc.path)

    return DesignResult(
        plan_doc=plan_doc,
        summary=iterate_result[:500],
    )


def stage_execute(
    *,
    plan_doc: PlanDocPath,
    objective: str,
) -> ExecuteResult:
    """Execute stage: implement + commit.

    Bundles implementation and commit using the decorated tools.

    Args:
        plan_doc: Validated PlanDocPath from design stage.
        objective: The original objective.

    Returns:
        ExecuteResult with status and commit info.
    """
    # Step 1: Implement plan (uses decorated tool)
    logger.info("Execute step 1/2: Implementing plan")
    impl_result = _implement_plan(
        plan_document_path=Path(plan_doc.path),
        query=objective,
    )

    # Step 2: Commit changes
    logger.info("Execute step 2/2: Committing changes")
    commit_result = _commit_changes(query="commit the changes")

    # Determine status from implementation result
    impl_lower = impl_result.lower()
    if "success" in impl_lower:
        status = "success"
    elif "partial" in impl_lower or "some" in impl_lower:
        status = "partial"
    else:
        status = "failed"

    # Extract commit hash (look for pattern like abc1234 or full SHA)
    commit_match = re.search(r"\b([a-f0-9]{7,40})\b", commit_result)
    commit_hash = commit_match.group(1) if commit_match else None

    # Extract files changed from implementation result
    # Pattern: look for file paths in the result
    file_pattern = re.compile(
        r"(?:^|\s)([\w/.-]+\.(?:py|md|json|yaml|yml|ts|js))", re.MULTILINE
    )
    files_changed = list(set(file_pattern.findall(impl_result)))

    logger.info("Execute complete: status=%s, commit=%s", status, commit_hash)

    return ExecuteResult(
        status=status,
        files_changed=files_changed,
        commit_hash=commit_hash,
    )
