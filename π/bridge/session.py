"""Async bridge for Claude Agent SDK integration.

This module provides a pure execution bridge for MCP tools.
No context access - all inputs are explicit parameters.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from π.config import COMMAND_MAP, get_stage_agent_options
from π.core.enums import Command, DocType
from π.support.directory import get_project_root
from π.workflow.observer import dispatch_message

if TYPE_CHECKING:
    from π.workflow.observer import WorkflowObserver

logger = logging.getLogger(__name__)

# Command → DocType mapping (only commands that produce tracked documents)
COMMAND_DOC_TYPE: dict[Command, DocType] = {
    Command.RESEARCH_CODEBASE: DocType.RESEARCH,
    Command.CREATE_PLAN: DocType.PLAN,
    Command.REVIEW_PLAN: DocType.PLAN,
    Command.ITERATE_PLAN: DocType.PLAN,
}

# Tools that create/modify files
_FILE_WRITE_TOOLS = frozenset({"Write", "Edit"})

# Commands that involve planning (not execution)
_PLANNING_COMMANDS = frozenset({
    Command.CREATE_PLAN,
    Command.REVIEW_PLAN,
    Command.ITERATE_PLAN,
})

# Module-level options cache (config, not workflow state)
_cached_options: ClaudeAgentOptions | None = None


def get_git_commit_hash(*, cwd: Path | None = None) -> str | None:
    """Get the latest commit hash from git.

    Args:
        cwd: Working directory for git command.

    Returns:
        Short commit hash or None if git fails.
    """
    cwd = cwd or get_project_root()
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def get_git_changed_files(*, cwd: Path | None = None) -> list[str]:
    """Get files changed in the latest commit.

    Args:
        cwd: Working directory for git command.

    Returns:
        List of changed file paths.
    """
    cwd = cwd or get_project_root()
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


def _get_default_options() -> ClaudeAgentOptions:
    """Get or create cached options for stage agents.

    Stage agents use STAGE_AGENT_TOOLS (no AskUserQuestion) so questions
    pass through to the orchestrator instead of blocking.
    """
    global _cached_options  # noqa: PLW0603
    if _cached_options is None:
        _cached_options = get_stage_agent_options(cwd=get_project_root())
    return _cached_options


@dataclass
class WriteTracker:
    """Tracks file writes during a single SDK session."""

    command: Command
    doc_writes: list[str] = field(default_factory=list)
    all_writes: list[str] = field(default_factory=list)

    @property
    def doc_type(self) -> DocType | None:
        """Get doc_type for this command (if any)."""
        return COMMAND_DOC_TYPE.get(self.command)

    def on_tool_use(self, file_path: str) -> None:
        """Record write from ToolUseBlock."""
        self.all_writes.append(file_path)
        if self.doc_type and "thoughts/shared/" in file_path:
            self.doc_writes.append(file_path)

    def get_doc_path(self) -> str | None:
        """Get the last tracked doc path that exists on disk."""
        for p in reversed(self.doc_writes):
            path = Path(p)
            full_path = path if path.is_absolute() else get_project_root() / p
            if full_path.exists():
                return str(full_path)
        return None

    def get_files_changed(self) -> list[str]:
        """Get all files that were written during this session."""
        return list(self.all_writes)


def _process_message(
    message: AssistantMessage,
    tracker: WriteTracker,
) -> str:
    """Process assistant message and return accumulated text."""
    block_text = ""
    for block in message.content:
        if isinstance(block, TextBlock):
            block_text += block.text
        elif isinstance(block, ToolUseBlock):
            if block.name in _FILE_WRITE_TOOLS and (
                file_path := block.input.get("file_path")
            ):
                tracker.on_tool_use(file_path)
        elif isinstance(block, ToolResultBlock) and block.is_error:
            logger.warning("Tool error: %s", block.content)
    return block_text


async def run_claude_session(
    *,
    options: ClaudeAgentOptions | None = None,
    observer: WorkflowObserver | None = None,
    session_id: str | None = None,
    document: Path | None = None,
    tool_command: Command,
    query: str,
) -> tuple[str, str, str | None, list[str]]:
    """Execute a Claude agent session asynchronously.

    Pure execution function - no context access. All inputs are explicit.

    Args:
        tool_command: The Command enum for tracking writes.
        query: The query/instruction for the agent.
        session_id: Optional session ID for resumption.
        document: Optional document path to include.
        options: Optional agent options override (for testing).
        observer: Optional observer to log stage agent events.

    Returns:
        Tuple of (result content, new session_id, doc_path or None, files_changed).

    Raises:
        ValueError: If tool_command is not in COMMAND_MAP.
        RuntimeError: If agent execution fails.
    """
    tracker = WriteTracker(command=tool_command)
    agent_id = f"stage:{tool_command.value}"

    # Build command string from slash command
    command = COMMAND_MAP.get(tool_command)
    if not command:
        raise ValueError(f"Invalid tool command: {tool_command}")

    # Add document path if provided
    if document:
        command += f" {document}"

    command += f" {query}"

    # Handle session resumption
    if session_id:
        logger.debug("Resuming session: %s", session_id)
        if tool_command in _PLANNING_COMMANDS:
            command = (
                f"Based on this feedback, continue with your planning task "
                f"(write or update the plan document, do NOT implement): {query}"
            )
        else:
            command = query

    logger.debug("Executing command: %s", command[:200])

    # Execute session
    effective_options = options or _get_default_options()
    result_content = ""
    new_session_id = ""
    last_text = ""

    async with ClaudeSDKClient(options=effective_options) as client:
        try:
            await client.query(command, session_id=session_id or "default")

            async for message in client.receive_response():
                # Dispatch to observer for logging (if provided)
                if observer:
                    dispatch_message(message, observer, agent_id=agent_id)

                if isinstance(message, ResultMessage):
                    if message.result:
                        new_session_id = message.session_id
                        result_content = message.result
                    logger.debug(
                        "Session complete: turns=%d, cost=$%.4f",
                        message.num_turns,
                        message.total_cost_usd or 0,
                    )
                    break
                elif isinstance(message, AssistantMessage):
                    text = _process_message(message, tracker)
                    if text:
                        last_text = text
        except Exception as e:
            logger.exception("Agent execution failed")
            raise RuntimeError(f"Agent execution failed: {e}") from e

    files_changed = tracker.get_files_changed()
    doc_path = tracker.get_doc_path()
    logger.debug(
        "Session result: session_id=%s, doc_path=%s, files_changed=%d",
        new_session_id,
        doc_path,
        len(files_changed),
    )

    return (result_content or last_text, new_session_id, doc_path, files_changed)
