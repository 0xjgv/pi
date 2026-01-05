"""DSPy-compatible workflow tools for π.

This module provides the 6 workflow stage tools that wrap Claude agent
task execution for use in DSPy ReAct agents.
"""

from __future__ import annotations

from pathlib import Path

from π.support.hitl import ConsoleInputProvider, create_ask_user_question_tool
from π.workflow.bridge import _execute_claude_task, workflow_tool
from π.workflow.context import Command, _get_ctx

# DSPy-compatible ask_user_question tool for workflow stages
ask_user_question = create_ask_user_question_tool(ConsoleInputProvider())


@workflow_tool(
    Command.RESEARCH_CODEBASE, phase_name="Researching codebase", doc_type="research"
)
def research_codebase(
    *,
    research_document_path: Path | str | None = None,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Research the codebase and return the results.

    Args:
        research_document_path: Optional path to the research document.
        query: The query to research the codebase (goal, question, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    return _execute_claude_task(
        path_to_document=Path(research_document_path)
        if research_document_path
        else None,
        tool_command=Command.RESEARCH_CODEBASE,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.CREATE_PLAN, phase_name="Creating plan", doc_type="plan")
def create_plan(
    *,
    research_document_path: Path | str,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Create a plan for the codebase.

    Args:
        research_document_path: Required path to the research document.
        query: The query to create a plan for the codebase (goal, question, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for validation in later stages
    _get_ctx().doc_paths[Command.CREATE_PLAN] = str(research_document_path)

    return _execute_claude_task(
        path_to_document=Path(research_document_path),
        tool_command=Command.CREATE_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.REVIEW_PLAN, phase_name="Reviewing plan", validate_plan=True)
def review_plan(
    *,
    plan_document_path: Path | str,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Review the plan for the codebase.

    Args:
        plan_document_path: Required path to the plan document.
        query: The query to review the plan (review, question, doubts, feedback, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for reference
    _get_ctx().doc_paths[Command.REVIEW_PLAN] = str(plan_document_path)

    return _execute_claude_task(
        path_to_document=Path(plan_document_path),
        tool_command=Command.REVIEW_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.ITERATE_PLAN, phase_name="Iterating plan", validate_plan=True)
def iterate_plan(
    *,
    plan_document_path: Path | str,
    review_feedback: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Iterate the plan for the codebase.

    Args:
        plan_document_path: Required path to the plan document.
        review_feedback: The review feedback to iterate the plan.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for reference
    _get_ctx().doc_paths[Command.ITERATE_PLAN] = str(plan_document_path)

    return _execute_claude_task(
        path_to_document=Path(plan_document_path),
        tool_command=Command.ITERATE_PLAN,
        session_id=session_id,
        query=review_feedback,
    )


@workflow_tool(
    Command.IMPLEMENT_PLAN, phase_name="Implementing plan", validate_plan=True
)
def implement_plan(
    *,
    plan_document_path: Path | str,
    query: str = "implement the plan",
    session_id: str | None = None,
) -> tuple[str, str]:
    """Implement the plan by executing all phases.

    Args:
        plan_document_path: Required path to the plan document.
        query: Implementation instructions or continuation context.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    _get_ctx().doc_paths[Command.IMPLEMENT_PLAN] = str(plan_document_path)

    return _execute_claude_task(
        path_to_document=Path(plan_document_path),
        tool_command=Command.IMPLEMENT_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.COMMIT, phase_name="Committing changes")
def commit_changes(
    *,
    query: str = "commit the changes",
    session_id: str | None = None,
) -> tuple[str, str]:
    """Commit the changes made during implementation.

    Args:
        query: Commit context or specific instructions.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    return _execute_claude_task(
        path_to_document=None,
        tool_command=Command.COMMIT,
        session_id=session_id,
        query=query,
    )
