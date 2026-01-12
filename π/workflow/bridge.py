"""Sync→async bridge for Claude Agent SDK integration.

This module provides the core execution bridge that allows synchronous DSPy
tools to invoke the async Claude Agent SDK.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from rich.console import Console

from π.config import get_agent_options
from π.core import AgentExecutionError
from π.state import set_current_status
from π.support.directory import get_project_root
from π.utils import speak
from π.workflow.context import (
    COMMAND_MAP,
    Command,
    _ctx,
    get_ctx,
    get_event_loop,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

    from π.workflow.types import DocType

# Re-export _ctx for backwards compatibility (tests import it from bridge.py)
__all__ = ["_ctx"]

# Logger and Console for the workflow
logger = logging.getLogger(__name__)
console = Console()


@contextmanager
def timed_phase(phase_name: str) -> Generator[None]:
    """Context manager that shows spinner during execution and timing after."""
    start = time.monotonic()
    logger.info(">>> Phase started: %s", phase_name)

    with console.status(f"[bold cyan]{phase_name}...") as status:
        set_current_status(status)
        try:
            yield
        finally:
            set_current_status(None)

    elapsed = time.monotonic() - start
    if elapsed < 60:
        time_str = f"{elapsed:.0f}s"
    else:
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins}m {secs}s"

    logger.info("<<< Phase complete: %s (%s)", phase_name, time_str)
    console.print(f"[green]✓[/green] {phase_name} ({time_str})")


def _log_tool_call(block: ToolUseBlock) -> None:
    """Log tool invocation details (skips read-only tools)."""
    if block.name in _READ_TOOLS:
        return
    input_str = str(block.input)
    input_preview = input_str[:2000] + "..." if len(input_str) > 2000 else input_str
    logger.debug("Tool: %s | Input: %s", block.name, input_preview)


def _log_tool_result(block: ToolResultBlock) -> None:
    """Log tool result details."""
    status = "error" if block.is_error else "ok"
    content_str = str(block.content)
    content_preview = (
        content_str[:300] + "..." if len(content_str) > 300 else content_str
    )
    logger.debug("Tool result [%s]: %s", status, content_preview)


def _log_result_metrics(message: ResultMessage) -> None:
    """Log session metrics from ResultMessage."""
    logger.debug(
        "Session metrics: turns=%d, duration=%dms, api_duration=%dms",
        message.num_turns,
        message.duration_ms,
        message.duration_api_ms,
    )
    if message.total_cost_usd is not None:
        logger.debug("Cost: $%.4f", message.total_cost_usd)
    if message.usage:
        logger.debug(
            "Tokens: in=%d, out=%d, cache_read=%d, cache_create=%d",
            message.usage.get("input_tokens", 0),
            message.usage.get("output_tokens", 0),
            message.usage.get("cache_read_input_tokens", 0),
            message.usage.get("cache_creation_input_tokens", 0),
        )


def _process_assistant_message(
    message: AssistantMessage,
    tracker: SessionWriteTracker | None = None,
) -> str:
    """Process assistant message content blocks and return accumulated text.

    Args:
        message: AssistantMessage containing content blocks
        tracker: Optional write tracker for capturing file writes

    Returns:
        Accumulated text from TextBlock content
    """
    block_text = ""
    for block in message.content:
        if isinstance(block, TextBlock):
            block_text += block.text
        elif isinstance(block, ToolUseBlock):
            _log_tool_call(block)
            if (
                tracker
                and block.name in _FILE_WRITE_TOOLS
                and (file_path := block.input.get("file_path"))
            ):
                tracker.on_tool_use(block.id, file_path)
        elif isinstance(block, ToolResultBlock):
            _log_tool_result(block)
            if tracker:
                tracker.on_tool_result(
                    block.tool_use_id, is_error=block.is_error or False
                )
    return block_text


def _get_agent_options() -> ClaudeAgentOptions:
    """Get agent options for the current context (evaluates cwd at runtime)."""
    ctx = get_ctx()
    if ctx.agent_options is not None:
        return ctx.agent_options
    options = get_agent_options(cwd=get_project_root())
    ctx.agent_options = options
    return options


# Document path patterns for extraction
_DOC_PATH_PATTERNS: dict[str, str] = {
    "research": r"(thoughts/shared/research/[\w\-]+\.md)",
    "plan": r"(thoughts/shared/plans/[\w\-]+\.md)",
}

# Tools that create/modify files
_FILE_WRITE_TOOLS = frozenset({"Write", "Edit"})

# Read-only tools excluded from debug logs to reduce noise.
# These don't mutate state, and SessionWriteTracker already captures writes explicitly.
_READ_TOOLS = frozenset({"Read", "Glob", "LS", "Grep"})


@dataclass
class SessionWriteTracker:
    """Tracks file writes during a single SDK session.

    Captures all writes per doc_type. Pending/confirm pattern excludes failed writes.
    """

    writes: dict[str, list[str]] = field(default_factory=dict)  # doc_type -> [paths]
    _pending: dict[str, tuple[str, str]] = field(
        default_factory=dict
    )  # tool_use_id -> (doc_type, path)

    def on_tool_use(self, tool_use_id: str, file_path: str) -> None:
        """Record pending write from ToolUseBlock."""
        if doc_type := self._infer_doc_type(file_path):
            self._pending[tool_use_id] = (doc_type, file_path)

    def on_tool_result(self, tool_use_id: str, *, is_error: bool) -> None:
        """Confirm or reject write based on ToolResultBlock."""
        if (pending := self._pending.pop(tool_use_id, None)) and not is_error:
            doc_type, path = pending
            self.writes.setdefault(doc_type, []).append(path)

    def get_paths(self, doc_type: str) -> list[str]:
        """Get all tracked paths for doc_type that exist on disk."""
        return [
            str(get_project_root() / p)
            for p in self.writes.get(doc_type, [])
            if (get_project_root() / p).exists()
        ]

    @staticmethod
    def _infer_doc_type(file_path: str) -> str | None:
        """Infer doc_type from file path pattern."""
        for doc_type, pattern in _DOC_PATH_PATTERNS.items():
            if re.search(pattern, file_path):
                return doc_type
        return None


def _extract_doc_path(
    result: str,
    doc_type: DocType,
    tracker: SessionWriteTracker | None = None,
) -> str | None:
    """Extract document path. Tracker path preferred, regex fallback.

    Args:
        result: Claude agent response text
        doc_type: Type of document ("research" or "plan")
        tracker: Optional write tracker with captured file paths

    Returns:
        Absolute path if found and exists, None otherwise
    """
    pattern = _DOC_PATH_PATTERNS.get(doc_type)
    if not pattern:
        logger.warning("Unknown doc_type: %s", doc_type)
        return None

    # Priority 1: Most recent tracked write
    if tracker:
        paths = tracker.get_paths(doc_type)
        if paths:
            logger.debug("Using tracked path: %s", paths[-1])
            return paths[-1]

    # Priority 2: Regex fallback
    if match := re.search(pattern, result):
        path = get_project_root() / match.group(1)
        if path.exists():
            logger.debug("Using regex path: %s", path)
            return str(path)

    return None


def _format_tool_result(
    *,
    doc_path: str | None,
    session_id: str,
    tool_name: str,
    result: str,
) -> str:
    """Format tool result for DSPy ReAct.

    Completion determined by document creation (verifiable).
    DSPy ReAct handles continuation from response context.

    Args:
        tool_name: Name of the tool (unused, kept for interface stability)
        doc_path: Extracted document path (if any)
        session_id: Session ID for continuation
        result: Raw result from Claude agent

    Returns:
        Formatted result with session context
    """
    return "\n".join(
        filter(
            bool,
            [
                f"<doc_path>{doc_path}</doc_path>" if doc_path else "",
                f"<session_id>{session_id}</session_id>",
                f"<tool_name>{tool_name}</tool_name>",
                f"<result>{result}</result>",
            ],
        )
    )


async def _run_claude_session(
    command: str,
    session_id: str | None,
) -> tuple[str, str, SessionWriteTracker]:
    """Execute a Claude agent session asynchronously.

    This is the core async logic extracted from _execute_claude_task to
    reduce function complexity.

    Args:
        command: The command string to execute
        session_id: Optional session ID for resumption

    Returns:
        Tuple of (result content, new session ID, write tracker)

    Raises:
        AgentExecutionError: If agent execution fails
    """
    tracker = SessionWriteTracker()
    last_text_content = ""
    result_content = ""
    new_session_id = ""

    async with ClaudeSDKClient(options=_get_agent_options()) as client:
        try:
            logger.debug(
                "%s session", "Using existing" if session_id else "Starting new"
            )
            await client.query(command, session_id=session_id or "default")

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    if message.result:
                        new_session_id = message.session_id
                        result_content = message.result
                    _log_result_metrics(message)
                    console.print(
                        f"\n[bold cyan]Result:[/bold cyan] {result_content}\n"
                    )
                    break
                elif isinstance(message, AssistantMessage):
                    block_text = _process_assistant_message(message, tracker)
                    if block_text:
                        last_text_content = block_text
        except Exception as e:
            raise AgentExecutionError(f"Agent execution failed: {e}") from e

    logger.debug("Session writes: %s", tracker.writes)

    return (
        result_content if result_content else last_text_content,
        new_session_id,
        tracker,
    )


def execute_claude_task(
    *,
    path_to_documents: list[Path | str] | None = None,
    session_id: str | None = None,
    tool_command: Command,
    query: str,
) -> tuple[str, str, SessionWriteTracker]:
    """Execute a Claude agent task synchronously.

    This is the main sync→async bridge that wraps _run_claude_session.

    Args:
        path_to_documents: Optional list of paths to documents for command.
        session_id: Optional session ID for resumption
        query: The query/instruction for the agent
        tool_command: The Command enum value

    Returns:
        Tuple of (result content, session ID, write tracker)

    Raises:
        ValueError: If tool_command is not in COMMAND_MAP
        AgentExecutionError: If agent execution fails
    """
    ctx = get_ctx()
    # We have noticed that the command (slash command) could also be in a different place
    # as it gets picked up as a skill. We need to identify if this is a future desired
    # behavior and if so, we need to update our slash commands to be skills as fallback.
    # Maybe skills are a better fit for this anyway.
    command = COMMAND_MAP.get(tool_command)
    if not command:
        raise ValueError(f"Invalid tool command: {tool_command}")

    # Prefix command with objective from context (only on initial calls)
    if ctx.objective and not session_id:
        command = f"{command}\n<objective>{ctx.objective}</objective>"

    if path_to_documents:
        paths_str = " ".join(str(p) for p in path_to_documents)
        command += f" {paths_str}"
    command += f" {query}"

    if session_id:
        logger.debug("Resuming session: %s", session_id)
        # When resuming, send only the follow-up query. The session_id passed to
        # ClaudeSDKClient.query() provides the conversation context from prior turns.
        #
        # For planning commands, prefix with explicit instruction to prevent the agent
        # from jumping straight to implementation when given user feedback.
        planning_commands = {
            Command.CREATE_PLAN,
            Command.REVIEW_PLAN,
            Command.ITERATE_PLAN,
        }
        if tool_command in planning_commands:
            command = (
                f"Based on this feedback, continue with your planning task "
                f"(write or update the plan document, do NOT implement): {query}"
            )
        else:
            command = query

    logger.debug("Tool call: %s", command)

    # For debugging purposes
    ctx.log_session_state()

    # Bridge Sync -> Async (reuse event loop across tool calls)
    return get_event_loop().run_until_complete(_run_claude_session(command, session_id))


def workflow_tool(
    command: Command,
    *,
    phase_name: str,
    doc_type: DocType | None = None,
    validate_plan: bool = False,
) -> Callable[
    [Callable[..., tuple[str, str, SessionWriteTracker]]], Callable[..., str]
]:
    """Decorator for workflow tools with session management, timing, and error handling.

    Session Preservation:
        Session IDs are stored in ExecutionContext.session_ids[command] for
        potential continuation. DSPy ReAct decides from context whether to
        continue the conversation or produce output fields.

    Args:
        command: The workflow command for session tracking.
        phase_name: Display name for the timed phase spinner.
        doc_type: If set, extract doc path from result (DocType: "plan" | "research").
        validate_plan: If True, validate that plan_document_path is not a research doc.

    Returns:
        Decorated function that handles all workflow boilerplate.
    """

    def decorator(
        func: Callable[..., tuple[str, str, SessionWriteTracker]],
    ) -> Callable[..., str]:
        @wraps(func)
        def wrapper(**kwargs: str | Path | None) -> str:
            logger.debug(">>> Entering %s tool", command.value)
            session = get_ctx()
            session_id = session.session_ids.get(command)

            # Validate and auto-inject plan document if required
            if validate_plan:
                plan_path = kwargs.get("plan_document_path")
                validated_path = session.get_or_validate_plan_path(plan_path)
                kwargs["plan_document_path"] = validated_path

            try:
                with timed_phase(phase_name):
                    # Pop session_id from kwargs if caller passed it (we inject our own)
                    kwargs.pop("session_id", None)
                    result, last_session_id, tracker = func(
                        session_id=session_id, **kwargs
                    )
                    logger.debug(
                        "%s result - session_id=%s, result=%s",
                        command.value,
                        last_session_id,
                        result[:200] if result else None,
                    )

                session.session_ids[command] = last_session_id
                speak(f"{phase_name.lower()} complete")

                if doc_type:
                    # Add ALL tracked paths to extracted_paths
                    tracked_paths = tracker.get_paths(doc_type)
                    if tracked_paths:
                        paths = session.extracted_paths.setdefault(doc_type, set())
                        paths.update(tracked_paths)
                        for p in tracked_paths:
                            session.extracted_results[p] = result

                    # Primary doc_path for completion marker (latest or regex fallback)
                    doc_path = _extract_doc_path(result, doc_type, tracker)
                    if doc_path:
                        # Also add regex-fallback path if not already tracked
                        paths = session.extracted_paths.setdefault(doc_type, set())
                        paths.add(doc_path)
                        session.extracted_results[doc_path] = result
                        # Document created = research complete, clear session
                        session.session_ids.pop(command, None)
                    return _format_tool_result(
                        session_id=last_session_id,
                        tool_name=command.value,
                        doc_path=doc_path,
                        result=result,
                    )
                return (
                    f"<session_id>{last_session_id}</session_id>\n"
                    f"<result>{result}</result>\n"
                )
            except AgentExecutionError as e:
                logger.exception("%s failed (AgentExecutionError)", command.value)
                return f"[ERROR] {e}"
            except Exception as e:
                logger.exception(
                    "%s failed (unexpected error: %s)", command.value, type(e).__name__
                )
                return f"[ERROR] Unexpected error: {type(e).__name__}: {e}"

        return wrapper

    return decorator
