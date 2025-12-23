import asyncio
import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from rich.console import Console
from rich.status import Status

from π.config import get_agent_options
from π.errors import AgentExecutionError
from π.utils import speak
from π.workflow.session import COMMAND_MAP, Command, WorkflowSession

# Context variables for per-invocation isolation (thread-safe, async-safe)
_agent_options_var: ContextVar[ClaudeAgentOptions] = ContextVar("agent_options")
_event_loop_var: ContextVar[asyncio.AbstractEventLoop] = ContextVar("event_loop")
_session_var: ContextVar[WorkflowSession] = ContextVar("session")

# Shared status for spinner suspension during user input
_current_status: ContextVar[Status | None] = ContextVar("current_status", default=None)


def get_current_status() -> Status | None:
    """Get the current spinner status (if any) for suspension during user input."""
    return _current_status.get()


# Logger and Console for the workflow
logger = logging.getLogger(__name__)
console = Console()


@contextmanager
def timed_phase(phase_name: str) -> Generator[None, None, None]:
    """Context manager that shows spinner during execution and timing after."""
    start = time.monotonic()
    with console.status(f"[bold cyan]{phase_name}...") as status:
        _current_status.set(status)
        try:
            yield
        finally:
            _current_status.set(None)
    elapsed = time.monotonic() - start

    if elapsed < 60:
        time_str = f"{elapsed:.0f}s"
    else:
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins}m {secs}s"

    console.print(f"[green]✓[/green] {phase_name} ({time_str})")


def _log_tool_call(block: ToolUseBlock) -> None:
    """Log tool invocation details."""
    input_preview = (
        str(block.input)[:100] + "..."
        if len(str(block.input)) > 100
        else str(block.input)
    )
    logger.debug("Tool: %s | Input: %s", block.name, input_preview)


def _log_tool_result(block: ToolResultBlock) -> None:
    """Log tool result details."""
    status = "error" if block.is_error else "ok"
    content_preview = (
        str(block.content)[:80] + "..."
        if len(str(block.content)) > 80
        else str(block.content)
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


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a reusable event loop for the current context."""
    try:
        loop = _event_loop_var.get()
        if not loop.is_closed():
            return loop
    except LookupError:
        pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _event_loop_var.set(loop)
    return loop


def _get_agent_options() -> ClaudeAgentOptions:
    """Get agent options for the current context (evaluates cwd at runtime)."""
    try:
        return _agent_options_var.get()
    except LookupError:
        options = get_agent_options(cwd=Path.cwd())
        _agent_options_var.set(options)
        return options


def _get_session() -> WorkflowSession:
    """Get workflow session for the current context."""
    try:
        return _session_var.get()
    except LookupError:
        session = WorkflowSession()
        _session_var.set(session)
        return session


def _execute_claude_task(
    *,
    path_to_document: Path | None = None,
    session_id: str | None = None,
    tool_command: Command,
    query: str,
) -> tuple[str, str]:
    command = COMMAND_MAP.get(tool_command)
    if not command:
        raise ValueError(f"Invalid tool command: {tool_command}")

    if path_to_document:
        command += f" {path_to_document}"
    command += f" {query}"

    if session_id:
        logger.debug("Resuming session: %s", session_id)
        command = query

    logger.debug("Tool call: %s", command)

    async def _run_async(sid: str | None) -> tuple[str, str]:
        last_text_content = ""
        result_content = ""
        last_message = None
        new_session_id = ""

        async with ClaudeSDKClient(options=_get_agent_options()) as client:
            try:
                if sid:
                    logger.debug("Using session ID: %s", sid)
                    await client.query(command, session_id=sid)
                else:
                    logger.debug("Starting new session")
                    await client.query(command)

                last_class_name = None
                async for message in client.receive_response():
                    current_class_name = message.__class__.__name__
                    last_message = message

                    if last_class_name != current_class_name:
                        logger.debug("Agent message type: %s", current_class_name)
                        last_class_name = current_class_name

                    if isinstance(message, ResultMessage):
                        if message.result:
                            new_session_id = message.session_id
                            result_content = message.result
                        _log_result_metrics(message)
                        # Log ResultMessage to console before returning
                        console.print(
                            f"\n[bold cyan]Result:[/bold cyan] {result_content}\n"
                        )
                        break
                    elif isinstance(message, AssistantMessage):
                        block_text = ""
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                block_text += block.text
                            elif isinstance(block, ToolUseBlock):
                                # can_use_tool callback handles AskUserQuestion tool use.
                                _log_tool_call(block)
                            elif isinstance(block, ToolResultBlock):
                                _log_tool_result(block)
                        if block_text:
                            last_text_content = block_text
            except Exception as e:
                raise AgentExecutionError(f"Agent execution failed: {e}") from e

        if last_message:
            logger.debug("Last message type: %s", last_message.__class__.__name__)

        return (
            result_content if result_content else last_text_content,
            new_session_id,
        )

    # For debugging purposes
    _get_session().log_session_state()

    # Bridge Sync -> Async (reuse event loop across tool calls)
    return _get_event_loop().run_until_complete(_run_async(session_id))


def clarify_goal(
    *,
    query: str,
) -> str:
    """
    Ask the agent to clarify the goal and return the results.

    Args:
        query: The query to clarify the goal (goal, question, etc.).

    Returns:
        A summary of the clarification + the file path of the clarification document or open questions to the agent.
    """
    # Auto-resume: check for existing session
    session_id = _get_session().get_resumable_session_id(Command.CLARIFY)
    logger.debug(
        f"Clarify goal tool command: {query}",
        {"session_id": session_id, "query": query},
    )

    try:
        with timed_phase("Clarifying goal"):
            result, last_session_id = _execute_claude_task(
                tool_command=Command.CLARIFY,
                session_id=session_id,
                query=query,
            )
            logger.debug(
                "Clarification result: %s",
                {"last_session_id": last_session_id, "result": result},
            )

        _get_session().set_session_id(Command.CLARIFY, last_session_id)
        speak("clarify complete")

        return f"Result: {result}, Clarification Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Clarification failed")
        return f"[ERROR] {e}"


def research_codebase(
    *,
    research_document_path: Path | str,
    query: str,
) -> str:
    """
    Research the codebase and return the results.

    Args:
        research_document_path: Optional path to the research document.
        query: The query to research the codebase (goal, question, etc.).

    Returns:
        A summary of the research + the file path of the research document or open questions to the agent.
    """
    logger.debug(">>> Entering research_codebase tool")
    try:
        research_document_path = Path(research_document_path)
        # Auto-resume: check for existing session
        session_id = _get_session().get_resumable_session_id(Command.RESEARCH_CODEBASE)
        logger.debug(
            "Research codebase - session_id=%s, research_document_path=%s, query=%s",
            session_id,
            research_document_path,
            query,
        )

        with timed_phase("Researching codebase"):
            result, last_session_id = _execute_claude_task(
                path_to_document=research_document_path,
                tool_command=Command.RESEARCH_CODEBASE,
                session_id=session_id,
                query=query,
            )
            logger.debug(
                "Research result - last_session_id=%s, result=%s",
                last_session_id,
                result[:200] if result else None,
            )

        _get_session().set_session_id(Command.RESEARCH_CODEBASE, last_session_id)
        speak("research complete")

        return f"Result: {result}, Research Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Research failed (AgentExecutionError)")
        return f"[ERROR] {e}"
    except Exception as e:
        # Catch ALL exceptions to ensure DSPy doesn't swallow errors silently
        logger.exception("Research failed (unexpected error: %s)", type(e).__name__)
        return f"[ERROR] Unexpected error: {type(e).__name__}: {e}"


def create_plan(
    *,
    research_document_path: Path | str,
    query: str,
) -> str:
    """
    Create a plan for the codebase.

    Args:
        query: The query to create a plan for the codebase (goal, question, etc.).
        research_document_path: Required path to the research document.

    Returns:
        A summary of the plan + the file path of the plan document or open questions to the agent.
    """
    logger.debug(">>> Entering create_plan tool")
    try:
        research_document_path = Path(research_document_path)
        # Auto-resume: check for existing session
        session_id = _get_session().get_resumable_session_id(Command.CREATE_PLAN)
        logger.debug(
            "Create plan - research_doc=%s, session_id=%s, query=%s",
            research_document_path,
            session_id,
            query,
        )

        with timed_phase("Creating plan"):
            result, last_session_id = _execute_claude_task(
                path_to_document=research_document_path,
                tool_command=Command.CREATE_PLAN,
                session_id=session_id,
                query=query,
            )
            logger.debug(
                "Plan result - last_session_id=%s, result=%s",
                last_session_id,
                result,
            )

        _get_session().set_doc_path(Command.CREATE_PLAN, str(research_document_path))
        _get_session().set_session_id(Command.CREATE_PLAN, last_session_id)
        speak("plan complete")

        return f"Result: {result}, Plan Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Planning failed (AgentExecutionError)")
        return f"[ERROR] {e}"
    except Exception as e:
        # Catch ALL exceptions to ensure DSPy doesn't swallow errors silently
        logger.exception("Planning failed (unexpected error: %s)", type(e).__name__)
        return f"[ERROR] Unexpected error: {type(e).__name__}: {e}"


def review_plan(
    *,
    plan_document_path: Path | str,
    query: str,
) -> str:
    """
    Review the plan for the codebase.

    Args:
        query: The query to review the plan for the codebase (review, question, doubts, feedback, etc.).
        plan_document_path: Required path to the plan document.

    Returns:
        A summary of the review (critical issues, high priority issues, optional items, clarification needed, key improvements, etc).
    """
    plan_document_path = Path(plan_document_path)
    # Auto-resume: check for existing session
    session_id = _get_session().get_resumable_session_id(Command.REVIEW_PLAN)
    logger.debug(
        "Review plan tool command: %s",
        {
            "plan_document_path": plan_document_path,
            "session_id": session_id,
            "query": query,
        },
    )

    # Validate: ensure we're not receiving the research doc by mistake
    _get_session().validate_plan_doc(str(plan_document_path))

    try:
        with timed_phase("Reviewing plan"):
            result, last_session_id = _execute_claude_task(
                path_to_document=plan_document_path,
                tool_command=Command.REVIEW_PLAN,
                session_id=session_id,
                query=query,
            )
            logger.debug(
                "Review result: %s",
                {"result": result, "last_session_id": last_session_id},
            )

        _get_session().set_doc_path(Command.REVIEW_PLAN, str(plan_document_path))
        _get_session().set_session_id(Command.REVIEW_PLAN, last_session_id)
        speak("review complete")

        return f"Result: {result}, Review Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Review failed")
        return f"[ERROR] {e}"


def iterate_plan(
    *,
    plan_document_path: Path | str,
    review_feedback: str,
) -> str:
    """
    Iterate the plan for the codebase.

    Args:
        review_feedback: The review feedback to iterate the plan for the codebase (critical issues, high priority issues, optional items, clarification needed, key improvements, etc).
        plan_document_path: Required path to the plan document.

    Returns:
        A summary of the iteration (updated plan document) or open questions to the agent.
    """
    plan_document_path = Path(plan_document_path)
    # Auto-resume: check for existing session
    session_id = _get_session().get_resumable_session_id(Command.ITERATE_PLAN)
    logger.debug(
        "Iterate plan tool command: %s",
        {
            "plan_document_path": plan_document_path,
            "review_feedback": review_feedback,
            "session_id": session_id,
        },
    )

    # Validate: ensure we're not receiving the research doc by mistake
    _get_session().validate_plan_doc(str(plan_document_path))

    try:
        with timed_phase("Iterating plan"):
            result, last_session_id = _execute_claude_task(
                path_to_document=plan_document_path,
                tool_command=Command.ITERATE_PLAN,
                query=review_feedback,
                session_id=session_id,
            )
            logger.debug(
                "Iteration result: %s",
                {"result": result, "last_session_id": last_session_id},
            )

        _get_session().set_doc_path(Command.ITERATE_PLAN, str(plan_document_path))
        _get_session().set_session_id(Command.ITERATE_PLAN, last_session_id)
        speak("iteration complete")

        return f"Result: {result}, Iteration Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Iteration failed")
        return f"[ERROR] {e}"
