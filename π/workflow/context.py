"""Execution context and state management for π workflow.

This module provides centralized execution state via ExecutionContext dataclass
and thread-safe context variable management.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from claude_agent_sdk import ClaudeAgentOptions

logger = logging.getLogger(__name__)

# Project root for command discovery
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Command(StrEnum):
    """Workflow stage commands."""

    CLARIFY = "clarify"
    RESEARCH_CODEBASE = "research_codebase"
    REVIEW_PLAN = "review_plan"
    CREATE_PLAN = "create_plan"
    ITERATE_PLAN = "iterate_plan"
    IMPLEMENT_PLAN = "implement_plan"
    COMMIT = "commit"


def build_command_map(
    *,
    command_dir: Path = PROJECT_ROOT / ".claude/commands",
) -> dict[Command, str]:
    """Build a command map from the command directory."""
    command_map: dict[Command, str] = {}
    if not command_dir.exists():
        return command_map

    for f in sorted(command_dir.glob("[0-9]_*.md")):
        try:
            # e.g., '1_research_codebase' -> 'RESEARCH_CODEBASE'
            command_name = f.stem.split("_", 1)[1].upper()
            if command_enum_member := getattr(Command, command_name, None):
                command_map[command_enum_member] = f"/{f.stem}"
        except (IndexError, AttributeError):
            logging.warning("Skipping malformed command file: %s", f.name)

    return command_map


COMMAND_MAP = build_command_map()


@dataclass
class ExecutionContext:
    """All execution state in one place."""

    agent_options: ClaudeAgentOptions | None = None
    event_loop: asyncio.AbstractEventLoop | None = None
    session_ids: dict[Command, str] = field(default_factory=dict)
    doc_paths: dict[Command, str] = field(default_factory=dict)
    extracted_paths: dict[str, str] = field(default_factory=dict)  # doc_type -> path

    def validate_plan_doc(self, plan_path: str) -> None:
        """Validate that plan_path is not the research document.

        This method prevents a common agent mistake: passing the research
        document instead of the plan document to implement_plan.

        Raises:
            ValueError: If plan_path matches the research document.
        """
        research_doc = self.doc_paths.get(Command.CREATE_PLAN, "")
        if research_doc and plan_path == research_doc:
            raise ValueError(
                "implement_plan requires the PLAN document, "
                f"not the research document.\nReceived: {plan_path}\n"
                "Hint: Use the plan document returned by create_plan."
            )

    def log_session_state(self) -> None:
        """Log all session IDs and document paths for debugging."""
        logger.debug("ExecutionContext state:")
        logger.debug("Session IDs:")
        for command, session_id in self.session_ids.items():
            logger.debug("  %s: %s", command.value, session_id or "(not set)")
        logger.debug("Document paths:")
        for command, doc_path in self.doc_paths.items():
            logger.debug("  %s: %s", command.value, doc_path or "(not set)")


# Single context variable for all execution state
_ctx: ContextVar[ExecutionContext | None] = ContextVar("ctx", default=None)


def _get_ctx() -> ExecutionContext:
    """Get or create the execution context."""
    ctx = _ctx.get()
    if ctx is None:
        ctx = ExecutionContext()
        _ctx.set(ctx)
    return ctx


def get_extracted_path(doc_type: str) -> str | None:
    """Get the last extracted and validated path for a document type.

    Use this instead of LLM-generated output fields to avoid hallucinated paths.

    Args:
        doc_type: Type of document ("research" or "plan")

    Returns:
        Validated absolute path if available, None otherwise
    """
    return _get_ctx().extracted_paths.get(doc_type)
