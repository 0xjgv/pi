import asyncio
import logging
import os
from pathlib import Path

import click
import dspy
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
)
from dotenv import load_dotenv

from π.agent import get_agent_options
from π.utils import setup_logging

load_dotenv()

THINKING_MODELS = {
    "low": "claude-haiku-4-5-20251001",
    "med": "claude-sonnet-4-5-20250929",
    "high": "claude-opus-4-5-20251101",
}

# Module-level logger
logger = logging.getLogger("π")


def configure_dspy(model: str = THINKING_MODELS["low"]) -> None:
    """Configure DSPy with the specified model."""
    try:
        lm = dspy.LM(
            api_base=os.getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
            api_key=os.getenv("CLIPROXY_API_KEY"),
            model=model,
        )
        dspy.configure(lm=lm)
    except Exception:
        logger.warning("DSPy LM not configured")


# --- The Tool Definition ---

COMMAND_MAP = {
    "research_codebase": "/1_research_codebase",
    "create_plan": "/2_create_plan",
    "implement_plan": "/3_implement_plan",
}


class SessionManager:
    """Manages session state for Claude task execution."""

    def __init__(self, commands: list[str]) -> None:
        self._by_command: dict[str, str] = dict.fromkeys(commands, "")
        self._by_path: dict[str, str] = dict.fromkeys(commands, "")

    def get_session_id(self, command: str) -> str:
        """Get the session ID for a command."""
        return self._by_command.get(command, "")

    def get_path(self, command: str) -> str:
        """Get the document path for a command."""
        return self._by_path.get(command, "")

    def set_session(
        self, command: str, session_id: str, path: str | None = None
    ) -> None:
        """Update session state for a command."""
        if session_id:
            self._by_command[command] = session_id
        if path:
            self._by_path[command] = path

    def __repr__(self) -> str:
        return f"SessionManager(commands={self._by_command}, paths={self._by_path})"


agent_options = get_agent_options(cwd=Path.cwd())


def execute_claude_task(
    *,
    session_manager: SessionManager,
    path_to_document: Path | None = None,
    session_id: str | None = None,
    tool_command: str,
    query: str,
) -> tuple[str, str]:
    command = COMMAND_MAP.get(tool_command)
    if not command:
        raise ValueError(f"Invalid tool command: {tool_command}")

    if path_to_document:
        command += f" {path_to_document}"
    command += f" {query}"

    # we resume the conversation
    previous_session_id = session_manager.get_session_id(tool_command)
    # session_id should be the same as the current tool_command session_id
    logger.debug("Session transition: %s -> %s", previous_session_id, session_id)
    is_valid_session_id = previous_session_id == session_id
    if is_valid_session_id:
        logger.debug("Resuming session: %s", session_id)
        command = query

    logger.debug("Tool call: %s", command)

    async def _run_async(session_id: str | None = None) -> tuple[str, str | None]:
        last_text_content = ""
        result_content = ""
        last_message = None

        async with ClaudeSDKClient(options=agent_options) as client:
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
                return f"Error executing agent: {e}", session_id

        logger.debug("Last message type: %s", last_message.__class__.__name__)

        return result_content if result_content else last_text_content, session_id

    # Bridge Sync -> Async
    result, session_id = asyncio.run(
        _run_async(session_id if is_valid_session_id else None)
    )

    if session_id:
        session_manager.set_session(
            tool_command,
            session_id,
            str(path_to_document) if path_to_document else None,
        )

    logger.debug("Session manager state: %s", session_manager)

    return result, session_id or session_id or ""


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
    setup_logging(verbose)
    model = THINKING_MODELS[thinking]
    configure_dspy(model)

    global agent_options
    agent_options = get_agent_options(cwd=Path.cwd(), model=model)

    session_manager = SessionManager(list(COMMAND_MAP.keys()))

    def research_codebase(
        *,
        session_id: str | None = None,
        query: str,
    ) -> str:
        """Research the codebase and return the results."""
        result, session_id = execute_claude_task(
            session_manager=session_manager,
            session_id=session_id,
            tool_command="research_codebase",
            query=query,
        )
        return f"Result: {result}, Research Session ID: {session_id}"

    def create_plan(
        *,
        session_id: str | None = None,
        research_document_path: Path,
        query: str,
    ) -> str:
        """Create a plan for the codebase."""
        result, session_id = execute_claude_task(
            session_manager=session_manager,
            path_to_document=research_document_path,
            tool_command="create_plan",
            session_id=session_id,
            query=query,
        )
        return f"Result: {result}, Plan Session ID: {session_id}"

    def implement_plan(
        *,
        session_id: str | None = None,
        plan_document_path: Path,
        query: str,
    ) -> str:
        """Implement the plan for the codebase."""
        # Validate: ensure we're not receiving the research doc by mistake
        research_doc_used = session_manager.get_path("create_plan")
        if research_doc_used and str(plan_document_path) == research_doc_used:
            raise ValueError(
                f"implement_plan requires the PLAN document, not the research document.\n"
                f"Received: {plan_document_path}\n"
                f"Hint: Use the plan document returned by create_plan."
            )

        result, session_id = execute_claude_task(
            session_manager=session_manager,
            path_to_document=plan_document_path,
            tool_command="implement_plan",
            session_id=session_id,
            query=query,
        )
        return f"Result: {result}, Implementation Session ID: {session_id}"

    click.echo(f"Starting ReAct Agent [{thinking}] with: '{objective}'")

    agent = dspy.ReAct(
        tools=[research_codebase, create_plan, implement_plan],
        signature=AgentTask,
    )
    result = agent(objective=objective)

    click.echo(f"\nFinal Answer: {result.output}")


if __name__ == "__main__":
    main()
