"""Sync→async bridge for Claude Agent SDK integration.

This module provides the core execution bridge that allows synchronous DSPy
tools to invoke the async Claude Agent SDK.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import contextmanager
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
    """Log tool invocation details."""
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


def _process_assistant_message(message: AssistantMessage) -> str:
    """Process assistant message content blocks and return accumulated text.

    Args:
        message: AssistantMessage containing content blocks

    Returns:
        Accumulated text from TextBlock content
    """
    block_text = ""
    for block in message.content:
        if isinstance(block, TextBlock):
            block_text += block.text
        elif isinstance(block, ToolUseBlock):
            _log_tool_call(block)
        elif isinstance(block, ToolResultBlock):
            _log_tool_result(block)
    return block_text


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a reusable event loop for the current context."""
    ctx = get_ctx()
    if ctx.event_loop is not None and not ctx.event_loop.is_closed():
        return ctx.event_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx.event_loop = loop
    return loop


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


def _extract_doc_path(result: str, doc_type: DocType) -> str | None:
    """Extract and validate document path from agent response.

    Args:
        result: Claude agent response text
        doc_type: Type of document ("research" or "plan")

    Returns:
        Absolute path if found and exists, None otherwise
    """
    pattern = _DOC_PATH_PATTERNS.get(doc_type)
    if not pattern:
        logger.warning("Unknown doc_type: %s", doc_type)
        return None

    if match := re.search(pattern, result):
        path = get_project_root() / match.group(1)
        if path.exists():
            logger.debug("Extracted and validated doc path: %s", path)
            return str(path)
        logger.debug("Extracted path does not exist: %s", path)
    return None


def _format_tool_result(
    *,
    result: str,
    session_id: str,
    doc_path: str | None,
    tool_name: str,
) -> str:
    """Format tool result for DSPy ReAct.

    Completion determined by document creation (verifiable).
    DSPy ReAct handles continuation from response context.

    Args:
        result: Raw result from Claude agent
        session_id: Session ID for continuation
        doc_path: Extracted document path (if any)
        tool_name: Name of the tool (unused, kept for interface stability)

    Returns:
        Formatted result with completion marker or session context
    """
    if doc_path:
        return (
            f"[TASK_COMPLETE] Document saved: {doc_path}\n"
            f"Proceed to produce output fields.\n\n"
            f"{result}"
        )
    # No heuristic - let DSPy decide from context
    return (
        f"Session: {session_id} | Tool: {tool_name}\n"
        f"Continue with follow-up if needed, or proceed to outputs.\n\n"
        f"{result}"
    )


async def _run_claude_session(
    command: str,
    session_id: str | None,
) -> tuple[str, str]:
    """Execute a Claude agent session asynchronously.

    This is the core async logic extracted from _execute_claude_task to
    reduce function complexity.

    Args:
        command: The command string to execute
        session_id: Optional session ID for resumption

    Returns:
        Tuple of (result content, new session ID)

    Raises:
        AgentExecutionError: If agent execution fails
    """
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
                    block_text = _process_assistant_message(message)
                    if block_text:
                        last_text_content = block_text
        except Exception as e:
            raise AgentExecutionError(f"Agent execution failed: {e}") from e

    return (
        result_content if result_content else last_text_content,
        new_session_id,
    )


def execute_claude_task(
    *,
    path_to_documents: list[Path | str] | None = None,
    session_id: str | None = None,
    tool_command: Command,
    query: str,
) -> tuple[str, str]:
    """Execute a Claude agent task synchronously.

    This is the main sync→async bridge that wraps _run_claude_session.

    Args:
        path_to_documents: Optional list of paths to documents for command.
        session_id: Optional session ID for resumption
        query: The query/instruction for the agent
        tool_command: The Command enum value

    Returns:
        Tuple of (result content, session ID)

    Raises:
        ValueError: If tool_command is not in COMMAND_MAP
        AgentExecutionError: If agent execution fails
    """
    command = COMMAND_MAP.get(tool_command)
    if not command:
        raise ValueError(f"Invalid tool command: {tool_command}")

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
    get_ctx().log_session_state()

    # Bridge Sync -> Async (reuse event loop across tool calls)
    return _get_event_loop().run_until_complete(
        _run_claude_session(command, session_id)
    )


def workflow_tool(
    command: Command,
    *,
    phase_name: str,
    doc_type: DocType | None = None,
    validate_plan: bool = False,
) -> Callable[[Callable[..., tuple[str, str]]], Callable[..., str]]:
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

    def decorator(func: Callable[..., tuple[str, str]]) -> Callable[..., str]:
        @wraps(func)
        def wrapper(**kwargs: str | Path | None) -> str:
            logger.debug(">>> Entering %s tool", command.value)
            session = get_ctx()
            session_id = session.session_ids.get(command)

            # Validate plan document if required
            if validate_plan and "plan_document_path" in kwargs:
                session.validate_plan_doc(str(kwargs["plan_document_path"]))

            try:
                with timed_phase(phase_name):
                    # Pop session_id from kwargs if caller passed it (we inject our own)
                    kwargs.pop("session_id", None)
                    result, last_session_id = func(session_id=session_id, **kwargs)
                    logger.debug(
                        "%s result - session_id=%s, result=%s",
                        command.value,
                        last_session_id,
                        result[:200] if result else None,
                    )

                session.session_ids[command] = last_session_id
                speak(f"{phase_name.lower()} complete")

                if doc_type:
                    doc_path = _extract_doc_path(result, doc_type)
                    if doc_path:
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
