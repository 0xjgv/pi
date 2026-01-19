"""Lightweight context for MCP workflow tools.

This module provides centralized state management for MCP tool execution,
tracking session IDs and document paths across tool calls.

Note: Config (agent_options) is handled by bridge module, not stored here.
Context holds only workflow state.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basic.observer import WorkflowObserver
    from π.core.enums import Command, DocType


@dataclass
class WorkflowContext:
    """Lightweight context for MCP workflow tools.

    Attributes:
        session_ids: Maps Command enum to session IDs for resumption.
        doc_paths: Maps DocType enum to produced document paths.
        objective: The workflow objective/goal being executed.
        observer: Optional observer for logging stage agent events.
    """

    session_ids: dict[Command, str] = field(default_factory=dict)
    doc_paths: dict[DocType, str] = field(default_factory=dict)
    objective: str | None = None
    observer: WorkflowObserver | None = None


_ctx: ContextVar[WorkflowContext | None] = ContextVar("mcp_workflow_ctx", default=None)


def get_workflow_ctx() -> WorkflowContext:
    """Get or create the workflow context.

    Returns:
        The current WorkflowContext, creating one if none exists.
    """
    ctx = _ctx.get()
    if ctx is None:
        ctx = WorkflowContext()
        _ctx.set(ctx)
    return ctx


def reset_workflow_ctx() -> None:
    """Reset the workflow context (for new workflows)."""
    _ctx.set(None)
