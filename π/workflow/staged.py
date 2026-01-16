"""Staged workflow tools with type-safe results.

These functions use DSPy ReAct agents with signature-driven outputs.
"""

from __future__ import annotations

import logging
import subprocess
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING

import dspy

if TYPE_CHECKING:
    from collections.abc import Callable

from π.core.enums import DocType, WorkflowStage
from π.support.directory import get_project_root
from π.workflow.callbacks import react_logging_callback
from π.workflow.context import get_ctx
from π.workflow.module import DesignSignature, ExecuteSignature, ResearchSignature
from π.workflow.tools import (
    ask_questions,
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


def require_lm[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator ensuring ExecutionContext.lm is configured before stage runs."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        ctx = get_ctx()
        if ctx.lm is None:
            msg = "ExecutionContext.lm not configured"
            raise ValueError(msg)
        return func(*args, **kwargs)

    return wrapper


def with_codebase_context[T: dspy.Signature](
    signature_class: type[T],
    context: str,
) -> type[T]:
    """Wrap a signature with codebase context in its instructions.

    DSPy uses signature.__doc__ as agent instructions. This factory
    creates a subclass with context appended to the docstring.

    Args:
        signature_class: Base signature class to wrap.
        context: Codebase context string (CLAUDE.md + deps).

    Returns:
        New signature class with context-aware instructions.
    """
    if not context:
        return signature_class

    class ContextAwareSignature(signature_class):
        pass

    base_doc = signature_class.__doc__ or ""
    ContextAwareSignature.__doc__ = f"""{base_doc}

## Codebase Context (use this to make targeted queries)
{context}

Strategy:
- Use ask_questions for quick factual queries the context doesn't answer
- Call research/design/execute tools ONCE with comprehensive, targeted queries
"""
    return ContextAwareSignature  # type: ignore[return-value]


@require_lm
def stage_research(*, objective: str) -> ResearchResult:
    """Research stage using ReAct agent.

    Args:
        objective: The objective to research.

    Returns:
        ResearchResult with aggregated docs and summaries from all tool calls.

    Raises:
        ValueError: If research did not produce a valid document.
    """
    ctx = get_ctx()
    lm = ctx.lm

    ctx.current_stage = WorkflowStage.RESEARCH
    ctx.objective = objective

    # Wrap signature with codebase context (from shared ExecutionContext)
    signature = with_codebase_context(ResearchSignature, ctx.codebase_context or "")

    agent = dspy.ReAct(
        tools=[research_codebase, ask_questions],
        signature=signature,
        max_iters=ctx.max_iters,
    )

    with dspy.context(lm=lm, callbacks=[react_logging_callback]):
        result = agent(objective=objective)

    # Use only tracked paths from tool calls (ignore LM output - may hallucinate)
    all_paths = ctx.extracted_paths.get(DocType.RESEARCH, set())
    all_results = ctx.extracted_results

    # Build list of validated ResearchDocPath objects
    research_docs = [ResearchDocPath(path=p) for p in all_paths]

    # Use only context-tracked summaries from actual tool calls
    summaries = [
        all_results[doc.path] for doc in research_docs if doc.path in all_results
    ]

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


@require_lm
def stage_design(
    *,
    research: ResearchResult,
    objective: str,
) -> DesignResult:
    """Design stage using ReAct agent.

    Args:
        research: Complete result from research stage with all docs and summaries.
        objective: The original objective.

    Returns:
        DesignResult from signature outputs.

    Raises:
        ValueError: If design did not produce a valid plan document.
    """
    ctx = get_ctx()
    lm = ctx.lm

    ctx.current_stage = WorkflowStage.DESIGN
    ctx.objective = objective

    # Keep extracted_paths for validate_plan_doc safety check
    research_paths = {doc.path for doc in research.research_docs}
    ctx.extracted_paths[DocType.RESEARCH] = research_paths

    # Pass research data as lists directly to match DesignSignature
    research_doc_paths = list(research_paths)
    research_summaries = research.summaries

    # Wrap signature with codebase context (from shared ExecutionContext)
    signature = with_codebase_context(DesignSignature, ctx.codebase_context or "")

    agent = dspy.ReAct(
        tools=[
            create_plan,
            review_plan,
            iterate_plan,
            ask_questions,
        ],
        signature=signature,
        max_iters=ctx.max_iters,
    )

    with dspy.context(lm=lm, callbacks=[react_logging_callback]):
        result = agent(
            research_doc_paths=research_doc_paths,
            research_summaries=research_summaries,
            objective=objective,
        )

    # Use tracked plan path from tool calls (ignore LM output - may hallucinate)
    plan_paths = ctx.extracted_paths.get(DocType.PLAN, set())
    if not plan_paths:
        msg = "Design did not produce a plan document"
        raise ValueError(msg)
    # Use most recent plan if multiple were created
    plan_path = max(plan_paths, key=lambda p: Path(p).stat().st_mtime)
    plan_doc = PlanDocPath(path=plan_path)

    logger.info("Design complete: plan=%s", plan_doc.path)

    return DesignResult(
        summary=result.plan_summary,
        plan_doc=plan_doc,
    )


def _get_git_changed_files(*, cwd: Path) -> list[str]:
    """Get changed files from git.

    Args:
        cwd: Working directory for git command.

    Returns:
        List of changed file paths (empty if none or git fails).
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


def _get_git_commit_hash(*, cwd: Path) -> str | None:
    """Get latest commit hash from git.

    Args:
        cwd: Working directory for git command.

    Returns:
        Short commit hash or None if git fails.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


@require_lm
def stage_execute(
    *,
    plan_doc: PlanDocPath,
    objective: str,
) -> ExecuteResult:
    """Execute stage using ReAct agent.

    Args:
        plan_doc: Validated PlanDocPath from design stage.
        objective: The original objective.

    Returns:
        ExecuteResult from signature outputs.
    """
    ctx = get_ctx()
    lm = ctx.lm

    ctx.current_stage = WorkflowStage.EXECUTE
    ctx.implementing_plan = plan_doc.path
    ctx.objective = objective

    # Wrap signature with codebase context (from shared ExecutionContext)
    signature = with_codebase_context(ExecuteSignature, ctx.codebase_context or "")

    agent = dspy.ReAct(
        tools=[
            implement_plan,
            commit_changes,
            ask_questions,
        ],
        signature=signature,
        max_iters=ctx.max_iters,
    )

    with dspy.context(lm=lm, callbacks=[react_logging_callback]):
        result = agent(
            plan_doc_path=plan_doc.path,
            objective=objective,
        )

    # Get files_changed and commit_hash from git (ignore LM output - may hallucinate)
    cwd = get_project_root()
    files_changed = _get_git_changed_files(cwd=cwd)
    commit_hash = _get_git_commit_hash(cwd=cwd)

    logger.info("Execute complete: status=%s, commit=%s", result.status, commit_hash)

    return ExecuteResult(
        files_changed=files_changed,
        commit_hash=commit_hash,
        status=result.status,
    )
