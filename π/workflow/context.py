"""Execution context and state management for π workflow.

This module provides centralized execution state via ExecutionContext dataclass
and thread-safe context variable management.
"""

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from π.workflow.types import PlanDocPath

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

    from π.support.hitl import QuestionAnswerer

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
    input_provider: QuestionAnswerer | None = None  # type: ignore[name-defined]

    def get_or_validate_plan_path(
        self,
        plan_path: str | Path | None = None,
    ) -> str:
        """Get plan path from context or validate provided path.

        If no path provided, auto-selects the most recently modified plan
        from extracted_paths["plan"]. Validates using PlanDocPath which
        checks directory, extension, existence, and date prefix.

        Args:
            plan_path: Optional path to validate. If None, uses latest from context.

        Returns:
            Validated absolute path string.

        Raises:
            ValueError: If no plan available or path is invalid.
        """
        if plan_path is None:
            plan_paths = self.extracted_paths.get("plan", set())
            if not plan_paths:
                raise ValueError("No plan document available. Run create_plan first.")
            # Select most recently modified plan
            plan_path = max(plan_paths, key=lambda p: Path(p).stat().st_mtime)

        # Validate using PlanDocPath (checks dir, extension, existence, date)
        validated = PlanDocPath(path=str(plan_path))
        return validated.path

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


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a reusable event loop for the current context.

    Returns:
        Event loop stored in ExecutionContext, creating one if needed.
    """
    ctx = get_ctx()
    if ctx.event_loop is not None and not ctx.event_loop.is_closed():
        return ctx.event_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx.event_loop = loop
    return loop
