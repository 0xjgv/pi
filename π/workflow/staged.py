"""Staged workflow tools with type-safe results.

These functions use DSPy ReAct agents with signature-driven outputs.
"""

from __future__ import annotations

import logging

import dspy

from π.config import MAX_ITERS
from π.workflow.module import DesignSignature, ExecuteSignature, ResearchSignature
from π.workflow.tools import (
    ask_user_question,
    commit_changes,
    create_plan,
    implement_plan,
    iterate_plan,
    research_codebase,
    review_plan,
)
from π.workflow.types import (
    DesignResult,
    ExecuteResult,
    PlanDocPath,
    ResearchDocPath,
    ResearchResult,
)

logger = logging.getLogger(__name__)


def stage_research(*, objective: str, lm: dspy.LM) -> ResearchResult:
    """Research stage using ReAct agent.

    Args:
        objective: The objective to research.
        lm: DSPy language model for ReAct agent.

    Returns:
        ResearchResult from signature outputs.

    Raises:
        ValueError: If research did not produce a valid document.
    """
    agent = dspy.ReAct(
        tools=[research_codebase, ask_user_question],
        signature=ResearchSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(objective=objective)

    research_doc = ResearchDocPath(path=result.research_doc_path)

    reason = (
        "Agent determined no implementation needed"
        if not result.needs_implementation
        else None
    )

    logger.info(
        "Research complete: needs_implementation=%s, doc=%s reason=%s",
        result.needs_implementation,
        research_doc.path,
        reason,
    )

    return ResearchResult(
        needs_implementation=result.needs_implementation,
        summary=result.research_summary,
        research_doc=research_doc,
        reason=reason,
    )


def stage_design(
    *,
    research_doc: ResearchDocPath,
    objective: str,
    lm: dspy.LM,
) -> DesignResult:
    """Design stage using ReAct agent.

    Args:
        research_doc: Validated ResearchDocPath from research stage.
        objective: The original objective.
        lm: DSPy language model for ReAct agent.

    Returns:
        DesignResult from signature outputs.

    Raises:
        ValueError: If design did not produce a valid plan document.
    """
    agent = dspy.ReAct(
        tools=[create_plan, review_plan, iterate_plan, ask_user_question],
        signature=DesignSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(
            objective=objective,
            research_doc_path=research_doc.path,
        )

    plan_doc = PlanDocPath(path=result.plan_doc_path)

    logger.info("Design complete: plan=%s", plan_doc.path)

    return DesignResult(
        summary=result.plan_summary,
        plan_doc=plan_doc,
    )


def stage_execute(
    *,
    plan_doc: PlanDocPath,
    objective: str,
    lm: dspy.LM,
) -> ExecuteResult:
    """Execute stage using ReAct agent.

    Args:
        plan_doc: Validated PlanDocPath from design stage.
        objective: The original objective.
        lm: DSPy language model for ReAct agent.

    Returns:
        ExecuteResult from signature outputs.
    """
    agent = dspy.ReAct(
        tools=[implement_plan, commit_changes, ask_user_question],
        signature=ExecuteSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(
            plan_doc_path=plan_doc.path,
            objective=objective,
        )

    # Parse files_changed from comma-separated string
    files_changed = [f.strip() for f in result.files_changed.split(",") if f.strip()]

    # Handle commit_hash
    commit_hash = result.commit_hash if result.commit_hash != "none" else None

    logger.info("Execute complete: status=%s, commit=%s", result.status, commit_hash)

    return ExecuteResult(
        files_changed=files_changed,
        commit_hash=commit_hash,
        status=result.status,
    )
