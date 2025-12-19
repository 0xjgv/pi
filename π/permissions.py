"""Permission callbacks for Claude Agent SDK tool execution control."""

import asyncio
import logging
from typing import Any

from claude_agent_sdk.types import (
    PermissionResult,
    PermissionResultAllow,
    ToolPermissionContext,
)
from rich.console import Console

from π.utils import speak

logger = logging.getLogger(__name__)
console = Console()


async def can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    context: ToolPermissionContext,
) -> PermissionResult:
    """
    Permission callback invoked before any tool execution.

    For AskUserQuestion: prompts the user and passes their response.
    For other tools: allows execution with logging.

    Args:
        tool_name: Name of the tool Claude wants to use.
        tool_input: Input parameters for the tool.
        context: Additional context including permission suggestions.

    Returns:
        PermissionResultAllow or PermissionResultDeny.
    """
    logger.debug("Tool permission request: %s", tool_name)

    # TODO: Keep track of the agent TodoWrite to display progress in the CLI
    if tool_name == "AskUserQuestion":
        question = tool_input.get("question", "Agent needs input:")
        console.print(f"\n[bold yellow]🤔 Agent asks:[/bold yellow] {question}")
        speak("questions")

        # Get user input (run sync input in thread to avoid blocking event loop)
        user_response = await asyncio.to_thread(
            console.input, "[bold green]Your response:[/bold green] "
        )

        logger.debug("User responded to AskUserQuestion: %s", user_response[:50])

        # Pass the user's response via updated_input
        # The tool will receive the original question + user's answer
        return PermissionResultAllow(
            updated_input={
                "question": question,
                "answer": user_response,
            }
        )

    # Log other tool calls
    input_preview = (
        str(tool_input)[:100] + "..." if len(str(tool_input)) > 100 else str(tool_input)
    )
    logger.debug("Allowing tool %s with input: %s", tool_name, input_preview)

    return PermissionResultAllow()
