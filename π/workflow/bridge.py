import asyncio
import logging
import re
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from functools import wraps
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

# Project root for command discovery
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Command(StrEnum):
    """Workflow stage commands."""

    CLARIFY = "clarify"
    RESEARCH_CODEBASE = "research_codebase"
    REVIEW_PLAN = "review_plan"
    CREATE_PLAN = "create_plan"
    ITERATE_PLAN = "iterate_plan"


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
    current_status: Status | None = None

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
                f"implement_plan requires the PLAN document, not the research document.\n"
                f"Received: {plan_path}\n"
                f"Hint: Use the plan document returned by create_plan."
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


def get_current_status() -> Status | None:
    """Get the current spinner status (if any) for suspension during user input."""
    return _get_ctx().current_status


def get_extracted_path(doc_type: str) -> str | None:
    """Get the last extracted and validated path for a document type.

    Use this instead of LLM-generated output fields to avoid hallucinated paths.

    Args:
        doc_type: Type of document ("research" or "plan")

    Returns:
        Validated absolute path if available, None otherwise
    """
    return _get_ctx().extracted_paths.get(doc_type)


# Logger and Console for the workflow
logger = logging.getLogger(__name__)
console = Console()


@contextmanager
def timed_phase(phase_name: str) -> Generator[None, None, None]:
    """Context manager that shows spinner during execution and timing after."""
    ctx = _get_ctx()
    start = time.monotonic()
    with console.status(f"[bold cyan]{phase_name}...") as status:
        ctx.current_status = status
        try:
            yield
        finally:
            ctx.current_status = None
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
    ctx = _get_ctx()
    if ctx.event_loop is not None and not ctx.event_loop.is_closed():
        return ctx.event_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ctx.event_loop = loop
    return loop


def _get_agent_options() -> ClaudeAgentOptions:
    """Get agent options for the current context (evaluates cwd at runtime)."""
    ctx = _get_ctx()
    if ctx.agent_options is not None:
        return ctx.agent_options
    options = get_agent_options(cwd=Path.cwd())
    ctx.agent_options = options
    return options


# Document path patterns for extraction
_DOC_PATH_PATTERNS: dict[str, str] = {
    "research": r"(thoughts/shared/research/[\w\-]+\.md)",
    "plan": r"(thoughts/shared/plans/[\w\-]+\.md)",
}


def _extract_doc_path(result: str, doc_type: str) -> str | None:
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
        path = Path.cwd() / match.group(1)
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
    """Format tool result with completion markers.

    Args:
        result: Raw result from Claude agent
        session_id: Session ID for continuation
        doc_path: Extracted document path (if any)
        tool_name: Name of the tool for continuation hint

    Returns:
        Formatted result with [COMPLETE] or [IN_PROGRESS] marker
    """
    if doc_path:
        return f"[COMPLETE] Document saved at: {doc_path}\n{result}"
    return (
        f"[IN_PROGRESS] Continue with session\n"
        f"Session ID: {session_id} (call {tool_name} again to continue)\n"
        f"{result}"
    )


def _execute_claude_task(
    *,
    path_to_document: Path | str | None = None,
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
    _get_ctx().log_session_state()

    # Bridge Sync -> Async (reuse event loop across tool calls)
    return _get_event_loop().run_until_complete(_run_async(session_id))


def workflow_tool(
    command: Command,
    *,
    phase_name: str,
    doc_type: str | None = None,
    validate_plan: bool = False,
) -> Callable[[Callable[..., tuple[str, str]]], Callable[..., str]]:
    """Decorator that handles session management, timing, logging, and error handling.

    Args:
        command: The workflow command for session tracking.
        phase_name: Display name for the timed phase spinner.
        doc_type: If set, extract doc path from result ("research" or "plan").
        validate_plan: If True, validate that plan_document_path is not a research doc.

    Returns:
        Decorated function that handles all workflow boilerplate.
    """

    def decorator(func: Callable[..., tuple[str, str]]) -> Callable[..., str]:
        @wraps(func)
        def wrapper(**kwargs: str | Path | None) -> str:
            logger.debug(">>> Entering %s tool", command.value)
            session = _get_ctx()
            session_id = session.session_ids.get(command)

            # Validate plan document if required
            if validate_plan:
                plan_path = kwargs.get("plan_document_path")
                if plan_path:
                    session.validate_plan_doc(str(plan_path))

            try:
                with timed_phase(phase_name):
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
                        session.extracted_paths[doc_type] = doc_path
                    return _format_tool_result(
                        result=result,
                        session_id=last_session_id,
                        doc_path=doc_path,
                        tool_name=command.value,
                    )
                return f"Result: {result}, Session ID: {last_session_id}"

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


@workflow_tool(
    Command.RESEARCH_CODEBASE, phase_name="Researching codebase", doc_type="research"
)
def research_codebase(
    *,
    research_document_path: Path | str | None = None,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Research the codebase and return the results.

    Args:
        research_document_path: Optional path to the research document.
        query: The query to research the codebase (goal, question, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    return _execute_claude_task(
        path_to_document=Path(research_document_path)
        if research_document_path
        else None,
        tool_command=Command.RESEARCH_CODEBASE,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.CREATE_PLAN, phase_name="Creating plan", doc_type="plan")
def create_plan(
    *,
    research_document_path: Path | str,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Create a plan for the codebase.

    Args:
        research_document_path: Required path to the research document.
        query: The query to create a plan for the codebase (goal, question, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for validation in later stages
    _get_ctx().doc_paths[Command.CREATE_PLAN] = str(research_document_path)

    return _execute_claude_task(
        path_to_document=Path(research_document_path),
        tool_command=Command.CREATE_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.REVIEW_PLAN, phase_name="Reviewing plan", validate_plan=True)
def review_plan(
    *,
    plan_document_path: Path | str,
    query: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Review the plan for the codebase.

    Args:
        plan_document_path: Required path to the plan document.
        query: The query to review the plan (review, question, doubts, feedback, etc.).
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for reference
    _get_ctx().doc_paths[Command.REVIEW_PLAN] = str(plan_document_path)

    return _execute_claude_task(
        path_to_document=Path(plan_document_path),
        tool_command=Command.REVIEW_PLAN,
        session_id=session_id,
        query=query,
    )


@workflow_tool(Command.ITERATE_PLAN, phase_name="Iterating plan", validate_plan=True)
def iterate_plan(
    *,
    plan_document_path: Path | str,
    review_feedback: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Iterate the plan for the codebase.

    Args:
        plan_document_path: Required path to the plan document.
        review_feedback: The review feedback to iterate the plan.
        session_id: Session ID for resumption (injected by decorator).

    Returns:
        Tuple of (result text, session ID).
    """
    # Store doc path for reference
    _get_ctx().doc_paths[Command.ITERATE_PLAN] = str(plan_document_path)

    return _execute_claude_task(
        path_to_document=Path(plan_document_path),
        tool_command=Command.ITERATE_PLAN,
        session_id=session_id,
        query=review_feedback,
    )
