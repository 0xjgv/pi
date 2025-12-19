import asyncio
import logging
from contextvars import ContextVar
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from rich.console import Console

from π.agent import get_agent_options
from π.errors import AgentExecutionError
from π.session import COMMAND_MAP, Command, WorkflowSession

# Context variables for per-invocation isolation (thread-safe, async-safe)
_agent_options_var: ContextVar[ClaudeAgentOptions] = ContextVar("agent_options")
_event_loop_var: ContextVar[asyncio.AbstractEventLoop] = ContextVar("event_loop")
_session_var: ContextVar[WorkflowSession] = ContextVar("session")

# Logger and Console for the workflow
logger = logging.getLogger(__name__)
console = Console()


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
                        # ResultMessage usually contains the structured output of a tool (e.g., complete_stage)
                        # or the final cost/summary.
                        if message.result:
                            new_session_id = message.session_id
                            result_content = message.result
                    elif isinstance(message, AssistantMessage):
                        block_text = ""
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                block_text += block.text
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
    session_id: str | None = None,
    query: str,
) -> str:
    """
    Ask the agent to clarify the goal and return the results.

    Args:
        query: The query to clarify the goal (goal, question, etc.).
        session_id: Optional session ID to resume a previous research session.

    Returns:
        A summary of the clarification + the file path of the clarification document or open questions to the agent.
    """
    if not _get_session().should_resume(Command.CLARIFY, session_id):
        session_id = None

    try:
        with console.status("[bold cyan]Clarifying goal..."):
            result, last_session_id = _execute_claude_task(
                tool_command=Command.CLARIFY,
                session_id=session_id,
                query=query,
            )
            logger.debug("Clarification result: %s", result)

        _get_session().set_session_id(Command.CLARIFY, last_session_id)

        return f"Result: {result}, Clarification Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Clarification failed")
        return f"[ERROR] {e}"


def research_codebase(
    *,
    session_id: str | None = None,
    query: str,
) -> str:
    """
    Research the codebase and return the results.

    Args:
        query: The query to research the codebase (goal, question, etc.).
        session_id: Optional session ID to resume a previous research session.

    Returns:
        A summary of the research + the file path of the research document or open questions to the agent.
    """
    if not _get_session().should_resume(Command.RESEARCH_CODEBASE, session_id):
        session_id = None

    try:
        with console.status("[bold cyan]Researching codebase..."):
            result, last_session_id = _execute_claude_task(
                tool_command=Command.RESEARCH_CODEBASE,
                session_id=session_id,
                query=query,
            )
            logger.debug("Research result: %s", result)

        _get_session().set_session_id(Command.RESEARCH_CODEBASE, last_session_id)

        return f"Result: {result}, Research Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Research failed")
        return f"[ERROR] {e}"


def create_plan(
    *,
    session_id: str | None = None,
    research_document_path: Path,
    query: str,
) -> str:
    """
    Create a plan for the codebase.

    Args:
        query: The query to create a plan for the codebase (goal, question, etc.).
        research_document_path: Required path to the research document.
        session_id: Optional session ID to resume a previous planning session.

    Returns:
        A summary of the plan + the file path of the plan document or open questions to the agent.
    """
    if not _get_session().should_resume(Command.CREATE_PLAN, session_id):
        session_id = None

    try:
        with console.status("[bold cyan]Creating plan..."):
            result, last_session_id = _execute_claude_task(
                path_to_document=research_document_path,
                tool_command=Command.CREATE_PLAN,
                session_id=session_id,
                query=query,
            )
            logger.debug("Plan result: %s", result)

        _get_session().set_doc_path(Command.CREATE_PLAN, str(research_document_path))
        _get_session().set_session_id(Command.CREATE_PLAN, last_session_id)

        return f"Result: {result}, Plan Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Planning failed")
        return f"[ERROR] {e}"


def implement_plan(
    *,
    session_id: str | None = None,
    plan_document_path: Path,
    query: str,
) -> str:
    """
    Implement the plan for the codebase.

    Args:
        query: The query to implement the plan for the codebase (goal, question, etc.).
        plan_document_path: Required path to the plan document.
        session_id: Optional session ID to resume a previous implementation session.

    Returns:
        A summary of the implementation or open questions to the agent.
    """
    # Validate: ensure we're not receiving the research doc by mistake
    _get_session().validate_plan_doc(str(plan_document_path))

    # If resuming a session, validate that the session ID matches the stored one.
    if not _get_session().should_resume(Command.IMPLEMENT_PLAN, session_id):
        session_id = None

    try:
        with console.status("[bold cyan]Implementing plan..."):
            result, last_session_id = _execute_claude_task(
                path_to_document=plan_document_path,
                tool_command=Command.IMPLEMENT_PLAN,
                session_id=session_id,
                query=query,
            )
            logger.debug("Implementation result: %s", result)

        _get_session().set_doc_path(Command.IMPLEMENT_PLAN, str(plan_document_path))
        _get_session().set_session_id(Command.IMPLEMENT_PLAN, last_session_id)

        return f"Result: {result}, Implementation Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Implementation failed")
        return f"[ERROR] {e}"
