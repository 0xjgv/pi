"""Sync→async bridge for Claude Agent SDK integration.

This module provides the core execution bridge that allows synchronous DSPy
tools to invoke the async Claude Agent SDK.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
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

from π.config import get_agent_options
from π.console import console
from π.core import AgentExecutionError
from π.state import (
    ArtifactEvent,
    emit_artifact_event,
    is_live_display_active,
    set_current_status,
)
from π.support.directory import get_project_root
from π.utils import speak
from π.workflow.context import (
    COMMAND_MAP,
    Command,
    get_ctx,
    get_event_loop,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

# Command → DocType mapping (only commands that produce tracked documents)
COMMAND_DOC_TYPE: dict[Command, str] = {
    Command.RESEARCH_CODEBASE: "research",
    Command.CREATE_PLAN: "plan",
}

logger = logging.getLogger(__name__)


@contextmanager
def timed_phase(phase_name: str) -> Generator[None]:
    """Context manager that shows spinner during execution and timing after."""
    start = time.monotonic()
    logger.info(">>> Phase started: %s", phase_name)
    emit_artifact_event(ArtifactEvent(event_type="phase_start", phase=phase_name))

    # Skip spinner if live display is active (it shows phase status)
    if is_live_display_active():
        yield
    else:
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

    emit_artifact_event(
        ArtifactEvent(event_type="phase_end", phase=phase_name, elapsed=elapsed)
    )
    logger.info("<<< Phase complete: %s (%s)", phase_name, time_str)
    console.print(f"[green]✓[/green] {phase_name} ({time_str})")


def _log_tool_call(block: ToolUseBlock) -> None:
    """Log tool invocation details with timing start."""
    # Start timing for all tools
    _tool_timing.start(block.id, block.name)

    # Skip logging for read-only tools (reduce noise)
    if block.name in _READ_TOOLS:
        return

    input_str = str(block.input)

    # Full logging for important tools (Skill, Task, Write, Edit)
    if block.name in _FULL_LOG_TOOLS:
        truncated = len(input_str) > _MAX_PAYLOAD_SIZE
        input_preview = (
            input_str[:_MAX_PAYLOAD_SIZE] + "..." if truncated else input_str
        )
        logger.info(
            "Tool START: %s | Input (%d chars%s): %s",
            block.name,
            len(input_str),
            ", truncated" if truncated else "",
            input_preview,
        )
    else:
        # Standard logging for other tools
        input_preview = input_str[:2000] + "..." if len(input_str) > 2000 else input_str
        logger.debug("Tool: %s | Input: %s", block.name, input_preview)


def _log_tool_result(block: ToolResultBlock) -> None:
    """Log tool result details with timing."""
    duration, tool_name = _tool_timing.end(block.tool_use_id)
    duration_str = f" ({duration:.2f}s)" if duration else ""
    status = "error" if block.is_error else "ok"
    content_str = str(block.content)

    # Full logging for important tools or errors
    if tool_name in _FULL_LOG_TOOLS or block.is_error:
        truncated = len(content_str) > _MAX_PAYLOAD_SIZE
        content_preview = (
            content_str[:_MAX_PAYLOAD_SIZE] + "..." if truncated else content_str
        )
        logger.info(
            "Tool END [%s]%s: %s (%d chars%s): %s",
            status,
            duration_str,
            tool_name or "unknown",
            len(content_str),
            ", truncated" if truncated else "",
            content_preview,
        )
    else:
        # Standard logging for other tools
        content_preview = (
            content_str[:300] + "..." if len(content_str) > 300 else content_str
        )
        logger.debug("Tool result [%s]%s: %s", status, duration_str, content_preview)


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
                emit_artifact_event(
                    ArtifactEvent(
                        event_type="file_start",
                        path=file_path,
                        doc_type=tracker.doc_type,
                    )
                )
        elif isinstance(block, ToolResultBlock):
            _log_tool_result(block)
            if tracker:
                # Capture pending path before on_tool_result pops it
                pending_path = tracker._pending.get(block.tool_use_id)
                tracker.on_tool_result(
                    block.tool_use_id, is_error=block.is_error or False
                )
                if pending_path:
                    event_type = "file_failed" if block.is_error else "file_done"
                    emit_artifact_event(
                        ArtifactEvent(
                            event_type=event_type,
                            path=pending_path,
                            doc_type=tracker.doc_type,
                        )
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


# Tools that create/modify files
_FILE_WRITE_TOOLS = frozenset({"Write", "Edit"})

# Read-only tools excluded from debug logs to reduce noise.
# These don't mutate state, and SessionWriteTracker already captures writes explicitly.
_READ_TOOLS = frozenset({"Read", "Glob", "LS", "Grep"})

# Tools that receive full context logging (important for debugging agent decisions)
_FULL_LOG_TOOLS = frozenset({"Skill", "Task", "Write", "Edit"})

# Maximum payload size before truncation (10KB)
_MAX_PAYLOAD_SIZE = 10 * 1024

# Commands that involve planning (not execution)
_PLANNING_COMMANDS = frozenset({Command.CREATE_PLAN, Command.REVIEW_PLAN})


@dataclass
class ToolTimingTracker:
    """Tracks tool execution timing for duration logging."""

    _start_times: dict[str, float] = field(default_factory=dict)
    _tool_names: dict[str, str] = field(default_factory=dict)

    def start(self, tool_use_id: str, tool_name: str) -> None:
        """Record start time for a tool invocation."""
        self._start_times[tool_use_id] = time.perf_counter()
        self._tool_names[tool_use_id] = tool_name

    def end(self, tool_use_id: str) -> tuple[float | None, str | None]:
        """Get duration and tool name for a completed tool invocation."""
        start = self._start_times.pop(tool_use_id, None)
        tool_name = self._tool_names.pop(tool_use_id, None)
        duration = time.perf_counter() - start if start else None
        return duration, tool_name


# Module-level timing tracker
_tool_timing = ToolTimingTracker()


@dataclass
class SessionWriteTracker:
    """Tracks file writes during a single SDK session.

    Command-based tracking: doc_type is determined by the command at creation,
    not inferred from file paths. Pending/confirm pattern excludes failed writes.
    """

    command: Command
    writes: list[str] = field(default_factory=list)
    _pending: dict[str, str] = field(default_factory=dict)  # tool_use_id -> path

    @property
    def doc_type(self) -> str | None:
        """Get doc_type for this command (if any)."""
        return COMMAND_DOC_TYPE.get(self.command)

    def on_tool_use(self, tool_use_id: str, file_path: str) -> None:
        """Record pending write from ToolUseBlock."""
        if self.doc_type and self._is_thoughts_path(file_path):
            self._pending[tool_use_id] = file_path

    def on_tool_result(self, tool_use_id: str, *, is_error: bool) -> None:
        """Confirm or reject write based on ToolResultBlock."""
        if (path := self._pending.pop(tool_use_id, None)) and not is_error:
            self.writes.append(path)

    def get_paths(self) -> list[str]:
        """Get all tracked paths that exist on disk."""
        result = []
        for p in self.writes:
            path = Path(p)
            # Handle both absolute and relative paths
            full_path = path if path.is_absolute() else get_project_root() / p
            if full_path.exists():
                result.append(str(full_path))
        return result

    @staticmethod
    def _is_thoughts_path(file_path: str) -> bool:
        """Check if path is in thoughts/shared/."""
        return "thoughts/shared/" in file_path


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
        doc_path: Extracted document path (if any)
        session_id: Session ID for continuation
        tool_name: Name of the tool for context
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
    command_str: str,
    session_id: str | None,
    tool_command: Command,
) -> tuple[str, str, SessionWriteTracker]:
    """Execute a Claude agent session asynchronously.

    This is the core async logic extracted from _execute_claude_task to
    reduce function complexity.

    Args:
        command_str: The command string to execute
        session_id: Optional session ID for resumption
        tool_command: The Command enum for tracking writes

    Returns:
        Tuple of (result content, new session ID, write tracker)

    Raises:
        AgentExecutionError: If agent execution fails
    """
    tracker = SessionWriteTracker(command=tool_command)
    last_text_content = ""
    result_content = ""
    new_session_id = ""

    async with ClaudeSDKClient(options=_get_agent_options()) as client:
        try:
            logger.debug(
                "%s session", "Using existing" if session_id else "Starting new"
            )
            await client.query(command_str, session_id=session_id or "default")

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

    return (result_content or last_text_content, new_session_id, tracker)


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
    # The command (slash command) could also be picked up as a skill.
    # TODO: Identify if skills should be the fallback for slash commands.
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
        if tool_command in _PLANNING_COMMANDS:
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
    return get_event_loop().run_until_complete(
        _run_claude_session(command, session_id, tool_command)
    )


def workflow_tool(
    command: Command,
    *,
    validate_plan: bool = False,
    phase_name: str,
) -> Callable[
    [Callable[..., tuple[str, str, SessionWriteTracker]]], Callable[..., str]
]:
    """Decorator for workflow tools with session management, timing, and error handling.

    Session Preservation:
        Session IDs are stored in ExecutionContext.session_ids[command] for
        potential continuation. DSPy ReAct decides from context whether to
        continue the conversation or produce output fields.

    Args:
        command: The workflow command for session tracking (also determines doc_type).
        phase_name: Display name for the timed phase spinner.
        validate_plan: If True, validate that plan_document_path is not a research doc.

    Returns:
        Decorated function that handles all workflow boilerplate.
    """
    # Get doc_type from command mapping (None for commands that don't produce docs)
    doc_type = COMMAND_DOC_TYPE.get(command)

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
                    tracked_paths = tracker.get_paths()
                    doc_path = tracked_paths[-1] if tracked_paths else None
                    if tracked_paths:
                        paths = session.extracted_paths.setdefault(doc_type, set())
                        paths.update(tracked_paths)
                        for p in tracked_paths:
                            session.extracted_results[p] = result
                        # Document created = complete, clear session
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
