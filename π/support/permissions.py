"""Permission callbacks for Claude Agent SDK tool execution control."""

import asyncio
import logging
from asyncio import wait_for
from typing import Any

from claude_agent_sdk.types import (
    PermissionResult,
    PermissionResultAllow,
    ToolPermissionContext,
)
from rich.console import Console

from π.state import get_current_status
from π.utils import speak

logger = logging.getLogger(__name__)
console = Console()

# Default timeout for user input (5 minutes)
USER_INPUT_TIMEOUT = 300.0


async def _get_input_with_timeout(prompt: str) -> str:
    """Get user input with timeout, returning placeholder on timeout/empty."""
    try:
        response = await wait_for(
            asyncio.to_thread(console.input, prompt),
            timeout=USER_INPUT_TIMEOUT,
        )
        return response.strip() or "[No response provided]"
    except TimeoutError:
        logger.warning("User input timed out after %s seconds", USER_INPUT_TIMEOUT)
        return "[No response - timed out]"


def _display_question(question: dict[str, Any]) -> None:
    """Display a single question with its options."""
    header = question.get("header", "Question")
    text = question.get("question", "")
    options = question.get("options", [])

    console.print(f"\n[bold yellow]🤔 {header}:[/bold yellow] {text}")

    if options:
        for i, opt in enumerate(options, 1):
            label = opt.get("label", "")
            desc = opt.get("description", "")
            console.print(f"  {i}. [bold]{label}[/bold] - {desc}")
        console.print(f"  {len(options) + 1}. [bold]Other[/bold] - Custom answer")


async def _parse_selection(user_input: str, options: list[dict[str, Any]]) -> str:
    """Parse user's numbered selection into label(s)."""
    selected_labels = []

    for raw_num in user_input.split(","):
        num_str = raw_num.strip()
        if not num_str:
            continue

        num = int(num_str)
        if 1 <= num <= len(options):
            selected_labels.append(options[num - 1]["label"])
        elif num == len(options) + 1:
            # "Other" selected
            custom = await _get_input_with_timeout("[green]Your answer:[/green] ")
            selected_labels.append(custom)

    return ", ".join(selected_labels) if selected_labels else "[Invalid selection]"


def _is_numeric_input(user_input: str) -> bool:
    """Check if input is numeric (possibly comma-separated)."""
    cleaned = user_input.strip().replace(",", "").replace(" ", "")
    return cleaned.isdigit() if cleaned else False


async def _collect_answer(question: dict[str, Any]) -> str:
    """Collect and parse answer for a single question."""
    options = question.get("options", [])
    multi_select = question.get("multiSelect", False)

    prompt = (
        "[bold green]Enter numbers (e.g. 1,3):[/bold green] "
        if multi_select
        else "[bold green]Enter number or text:[/bold green] "
    )

    user_input = await _get_input_with_timeout(prompt)

    if user_input.startswith("["):  # Timeout/error placeholder
        return user_input

    if options and _is_numeric_input(user_input):
        return await _parse_selection(user_input, options)

    return user_input


async def _handle_ask_user_question(
    tool_input: dict[str, Any],
) -> PermissionResultAllow:
    """Handle AskUserQuestion tool with structured questions/answers."""
    questions = tool_input.get("questions", [])

    # Suspend spinner during user input
    status = get_current_status()
    if status:
        status.stop()

    speak("questions")

    try:
        if not questions:
            # Fallback for malformed input
            console.print(
                "\n[bold yellow]🤔 Agent asks:[/bold yellow] Agent needs input"
            )
            response = await _get_input_with_timeout(
                "[bold green]Your response:[/bold green] "
            )
            return PermissionResultAllow(
                updated_input={"questions": [], "answers": {"": response}}
            )

        # Collect answers for each question
        answers: dict[str, str] = {}
        for q in questions:
            _display_question(q)
            question_text = q.get("question", "")
            answers[question_text] = await _collect_answer(q)

        logger.debug("User responded to AskUserQuestion: %s", str(answers)[:100])

        return PermissionResultAllow(
            updated_input={"questions": questions, "answers": answers}
        )
    finally:
        # Resume spinner after all questions answered
        if status:
            status.start()


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
        return await _handle_ask_user_question(tool_input)

    # Log other tool calls
    input_preview = (
        str(tool_input)[:100] + "..." if len(str(tool_input)) > 100 else str(tool_input)
    )
    logger.debug("Allowing tool %s with input: %s", tool_name, input_preview)

    return PermissionResultAllow()
