"""Staged workflow tools with type-safe results.

These functions use DSPy ReAct agents with signature-driven outputs.
"""

from __future__ import annotations

import logging

import dspy

from π.core import MAX_ITERS
from π.workflow.callbacks import LoggingCallback
from π.workflow.context import get_ctx
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

# Register logging callback globally (idempotent - safe to import multiple times)
dspy.configure(callbacks=[LoggingCallback()])


def stage_research(*, objective: str, lm: dspy.LM) -> ResearchResult:
    """Research stage using ReAct agent.

    Args:
        objective: The objective to research.
        lm: DSPy language model for ReAct agent.

    Returns:
        ResearchResult with aggregated docs and summaries from all tool calls.

    Raises:
        ValueError: If research did not produce a valid document.
    """
    # Set context for ask_user_question
    ctx = get_ctx()
    ctx.current_stage = "research"
    ctx.objective = objective

    agent = dspy.ReAct(
        tools=[research_codebase, ask_user_question],
        signature=ResearchSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(objective=objective)

    # Aggregate all research from tool calls during agent execution
    all_paths = ctx.extracted_paths.get("research", set())
    all_results = ctx.extracted_results

    # Include agent's final output docs (may already be in extracted_paths)
    all_paths.update(result.research_doc_paths)

    # Build list of validated ResearchDocPath objects
    research_docs = [ResearchDocPath(path=p) for p in sorted(all_paths)]

    # Build list of summaries: agent summaries first, then context-tracked ones
    summaries = list(result.research_summaries)
    for doc in research_docs:
        if doc.path in all_results and all_results[doc.path] not in summaries:
            summaries.append(all_results[doc.path])

    # Determine reason based on agent's explicit task_status and needs_implementation
    if not result.needs_implementation:
        reason = "Agent determined no implementation needed"
    elif result.task_status == "needs_clarification":
        reason = "Agent requires user clarification"
    else:
        reason = None

    logger.info(
        "Research complete: needs_impl=%s, docs=%d, status=%s, reason=%s",
        result.needs_implementation,
        len(research_docs),
        result.task_status,
        reason,
    )

    return ResearchResult(
        needs_implementation=result.needs_implementation,
        research_docs=research_docs,
        summaries=summaries,
        reason=reason,
    )


def stage_design(
    *,
    research: ResearchResult,
    objective: str,
    lm: dspy.LM,
) -> DesignResult:
    """Design stage using ReAct agent.

    Args:
        research: Complete result from research stage with all docs and summaries.
        objective: The original objective.
        lm: DSPy language model for ReAct agent.

    Returns:
        DesignResult from signature outputs.

    Raises:
        ValueError: If design did not produce a valid plan document.
    """
    # Set context for ask_user_question (runtime state only)
    ctx = get_ctx()
    ctx.current_stage = "design"
    ctx.objective = objective

    # Keep extracted_paths for validate_plan_doc safety check
    research_paths = {doc.path for doc in research.research_docs}
    ctx.extracted_paths["research"] = research_paths

    # Pass research data as lists directly to match DesignSignature
    research_doc_paths = list(research_paths)
    research_summaries = research.summaries

    agent = dspy.ReAct(
        tools=[create_plan, review_plan, iterate_plan, ask_user_question],
        signature=DesignSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(
            research_doc_paths=research_doc_paths,
            research_summaries=research_summaries,
            objective=objective,
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
    # Set context for ask_user_question
    ctx = get_ctx()
    ctx.extracted_paths.setdefault("plan", set()).add(plan_doc.path)
    ctx.current_stage = "execute"
    ctx.objective = objective

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
