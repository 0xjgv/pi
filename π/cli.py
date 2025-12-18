import asyncio
import logging
import os
from pathlib import Path

import click
import dspy
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from dotenv import load_dotenv
from rich.console import Console

from π.agent import get_agent_options
from π.session import COMMAND_MAP, Command, WorkflowSession
from π.utils import setup_logging

THINKING_MODELS = {
    "low": "claude-haiku-4-5-20251001",
    "med": "claude-sonnet-4-5-20250929",
    "high": "claude-opus-4-5-20251101",
}

# Module-level logger
logger = logging.getLogger("π")
console = Console()


class AgentExecutionError(Exception):
    """Raised when the Claude agent fails to execute a task."""

    pass


# Load environment variables from .env file
load_dotenv()

# Lazy-initialized state
_event_loop: asyncio.AbstractEventLoop | None = None
_agent_options: ClaudeAgentOptions | None = None
_session: WorkflowSession | None = None


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a reusable event loop for the CLI session."""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop


def _get_agent_options() -> ClaudeAgentOptions:
    """Lazy initialization of agent options (evaluates cwd at runtime)."""
    global _agent_options
    if _agent_options is None:
        _agent_options = get_agent_options(cwd=Path.cwd())
    return _agent_options


def _get_session() -> WorkflowSession:
    """Lazy initialization of workflow session."""
    global _session
    if _session is None:
        _session = WorkflowSession()
    return _session


def configure_dspy(model: str = THINKING_MODELS["low"]) -> None:
    """Configure DSPy with the specified model."""
    try:
        lm = dspy.LM(
            api_base=os.getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
            api_key=os.getenv("CLIPROXY_API_KEY"),
            model=model,
        )
        dspy.configure(lm=lm)
    except Exception as e:
        logger.warning("DSPy LM not configured: %s", e, exc_info=True)


# --- Tool Definitions ---


def execute_claude_task(
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

    async def _run_async(session_id: str | None = None) -> tuple[str, str | None]:
        last_text_content = ""
        result_content = ""
        last_message = None

        async with ClaudeSDKClient(options=_get_agent_options()) as client:
            try:
                if session_id:
                    logger.debug("Using session ID: %s", session_id)
                    await client.query(command, session_id=session_id)
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
                            session_id = message.session_id
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

        return result_content if result_content else last_text_content, session_id

    # Bridge Sync -> Async (reuse event loop across tool calls)
    result, session_id = _get_event_loop().run_until_complete(_run_async(session_id))

    return result, session_id or ""


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
            result, last_session_id = execute_claude_task(
                tool_command=Command.RESEARCH_CODEBASE,
                session_id=session_id,
                query=query,
            )

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
            result, last_session_id = execute_claude_task(
                path_to_document=research_document_path,
                tool_command=Command.CREATE_PLAN,
                session_id=session_id,
                query=query,
            )

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
            result, last_session_id = execute_claude_task(
                path_to_document=plan_document_path,
                tool_command=Command.IMPLEMENT_PLAN,
                session_id=session_id,
                query=query,
            )

        _get_session().set_doc_path(Command.IMPLEMENT_PLAN, str(plan_document_path))
        _get_session().set_session_id(Command.IMPLEMENT_PLAN, last_session_id)

        return f"Result: {result}, Implementation Session ID: {last_session_id}"
    except AgentExecutionError as e:
        logger.exception("Implementation failed")
        return f"[ERROR] {e}"


# --- ReAct Agent Module ---


class AgentTask(dspy.Signature):
    """Answer the objective using the available tools."""

    objective: str = dspy.InputField()
    output: str = dspy.OutputField()


# --- Execution ---


@click.command()
@click.argument("objective")
@click.option(
    "--thinking",
    "-t",
    type=click.Choice(["low", "med", "high"]),
    default="low",
    help="Thinking level: low=haiku (default), med=sonnet, high=opus",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging",
)
def main(objective: str, thinking: str, verbose: bool) -> None:
    """Run the ReAct agent with the given OBJECTIVE."""
    configure_dspy(THINKING_MODELS[thinking])
    setup_logging(verbose)

    click.echo(f"Starting ReAct Agent [{thinking}] with: '{objective}'")

    agent = dspy.ReAct(
        tools=[research_codebase, create_plan, implement_plan],
        signature=AgentTask,
    )
    result = agent(objective=objective)

    click.echo(f"\nFinal Answer: {result.output}")


if __name__ == "__main__":
    main()
