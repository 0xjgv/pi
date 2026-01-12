"""DSPy-compatible workflow tools for π.

This module provides the 6 workflow stage tools that wrap Claude agent
task execution for use in DSPy ReAct agents.
"""

from __future__ import annotations

from pathlib import Path

from π.support.aitl import create_ask_questions_tool
from π.workflow.bridge import SessionWriteTracker, execute_claude_task, workflow_tool
from π.workflow.context import Command

# DSPy-compatible ask_questions tool for workflow stages
# No explicit provider - uses context at runtime, falls back to AgentQuestionAnswerer
ask_questions = create_ask_questions_tool()


@workflow_tool(
    Command.RESEARCH_CODEBASE, phase_name="Researching codebase", doc_type="research"
)
def research_codebase(
    *,
    session_id: str | None = None,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Research the codebase and return the results.

    Args:
        query: The query to research the codebase (goal, question, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        tool_command=Command.RESEARCH_CODEBASE,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.CREATE_PLAN, phase_name="Creating plan", doc_type="plan")
def create_plan(
    *,
    research_document_paths: list[Path | str],
    session_id: str | None = None,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Create a plan for the codebase.

    Args:
        query: The query to create a plan for the codebase (goal, question, etc.).
        research_document_paths: Required paths to the research documents.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        path_to_documents=research_document_paths,
        tool_command=Command.CREATE_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.REVIEW_PLAN, phase_name="Reviewing plan", validate_plan=True)
def review_plan(
    *,
    plan_document_path: Path | str,
    session_id: str | None = None,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Review the plan for the codebase.

    Args:
        query: The query to review the plan (review, question, doubts, feedback, etc.).
        session_id: Session ID for resumption (injected by decorator).
        plan_document_path: Required path to the plan document.

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        path_to_documents=[Path(plan_document_path)],
        tool_command=Command.REVIEW_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.ITERATE_PLAN, phase_name="Iterating plan", validate_plan=True)
def iterate_plan(
    *,
    plan_document_path: Path | str,
    session_id: str | None = None,
    review_feedback: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Iterate the plan for the codebase.

    Args:
        review_feedback: The review feedback to iterate the plan.
        plan_document_path: Required path to the plan document.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        path_to_documents=[Path(plan_document_path)],
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
    session_id: str | None = None,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Implement the plan by executing all phases.

    Args:
        plan_document_path: Required path to the plan document.
        query: Implementation instructions or continuation context.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        path_to_documents=[Path(plan_document_path)],
        tool_command=Command.IMPLEMENT_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.COMMIT, phase_name="Committing changes")
def commit_changes(
    *,
    session_id: str | None = None,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Commit the changes made during implementation.

    Args:
        query: Commit context or additional specific instructions.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    return execute_claude_task(
        tool_command=Command.COMMIT,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.WRITE_CLAUDE_MD, phase_name="Updating documentation")
def write_claude_md(
    *,
    session_id: str | None = None,
    git_diff_context: str,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Update CLAUDE.md based on codebase changes.

    Args:
        session_id: Session ID for resumption (injected by decorator).
        git_diff_context: Summary of changes since last doc sync.
        query: Specific instructions for what to update.

    Returns:
        Tuple of (result text, session ID, write tracker).
    """
    full_query = (
        f"Based on the following recent codebase changes, update CLAUDE.md:\n\n"
        f"## Changes Since Last Sync\n{git_diff_context}\n\n"
        f"## Update Instructions\n{query}"
    )
    return execute_claude_task(
        tool_command=Command.WRITE_CLAUDE_MD,
        session_id=session_id,
        query=full_query,
    )
