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

    from π.support.hitl import HumanInputProvider

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
    WRITE_CLAUDE_MD = "write_claude_md"  # Non-numbered command


def build_command_map(
    *,
    command_dir: Path = PROJECT_ROOT / ".claude/commands",
) -> dict[Command, str]:
    """Build a command map from the command directory."""
    command_map: dict[Command, str] = {}
    if not command_dir.exists():
        return command_map

    # Numbered commands (existing pattern: 1_research_codebase.md)
    for f in sorted(command_dir.glob("[0-9]_*.md")):
        try:
            # e.g., '1_research_codebase' -> 'RESEARCH_CODEBASE'
            command_name = f.stem.split("_", 1)[1].upper()
            if command_enum_member := getattr(Command, command_name, None):
                command_map[command_enum_member] = f"/{f.stem}"
        except (IndexError, AttributeError):
            logging.warning("Skipping malformed command file: %s", f.name)

    # Non-numbered commands (explicit mapping)
    non_numbered = {
        Command.WRITE_CLAUDE_MD: "write-claude-md",
    }
    for cmd, filename in non_numbered.items():
        cmd_file = command_dir / f"{filename}.md"
        if cmd_file.exists():
            command_map[cmd] = f"/{filename}"

    return command_map


COMMAND_MAP = build_command_map()


@dataclass
class ExecutionContext:
    """All execution state in one place."""

    agent_options: ClaudeAgentOptions | None = None
    event_loop: asyncio.AbstractEventLoop | None = None
    session_ids: dict[Command, str] = field(default_factory=dict)
    extracted_paths: dict[str, set[str]] = field(default_factory=dict)
    extracted_results: dict[str, str] = field(default_factory=dict)
    # Auto-answer support fields
    objective: str | None = None
    current_stage: str | None = None
    input_provider: HumanInputProvider | None = None  # type: ignore[name-defined]

    def validate_plan_doc(self, plan_path: Path | str) -> None:
        """Validate that plan_path is not a research document.

        This method prevents a common agent mistake: passing a research
        document instead of the plan document to implement_plan.

        Raises:
            ValueError: If plan_path is in the set of research documents.
        """
        research_paths = self.extracted_paths.get("research", set())
        if str(plan_path) in research_paths:
            raise ValueError(
                "implement_plan requires the PLAN document, "
                f"not a research document.\nReceived: {plan_path}\n"
                "Hint: Use the plan document returned by create_plan."
            )

    def log_session_state(self) -> None:
        """Log all session IDs and extracted paths for debugging."""
        logger.debug("ExecutionContext state:")
        logger.debug("Session IDs:")
        for command, session_id in self.session_ids.items():
            logger.debug("  %s: %s", command.value, session_id or "(not set)")
        logger.debug("Extracted paths:")
        for doc_type, paths in self.extracted_paths.items():
            logger.debug("  %s: %s", doc_type, paths)
        logger.debug("Extracted results: %d", len(self.extracted_results))
        for path in self.extracted_results:
            logger.debug("  %s", path)


# Single context variable for all execution state
_ctx: ContextVar[ExecutionContext | None] = ContextVar("ctx", default=None)


def get_ctx() -> ExecutionContext:
    """Get or create the execution context."""
    ctx = _ctx.get()
    if ctx is None:
        ctx = ExecutionContext()
        _ctx.set(ctx)
    return ctx
