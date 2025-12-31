"""Human-in-the-loop (HITL) providers for π workflow."""

import logging
from typing import Protocol

from rich.console import Console
from rich.prompt import Prompt

from π.utils import speak

logger = logging.getLogger(__name__)


class HumanInputProvider(Protocol):
    """Protocol for human input providers.

    Implement this protocol to create custom HITL providers
    for different interfaces (CLI, web, Slack, etc.).
    """

    def ask(self, question: str) -> str:
        """Ask human a question and return their response.

        Args:
            question: The question to ask the human

        Returns:
            The human's response as a string
        """
        ...


class ConsoleInputProvider:
    """Console-based human input provider with validation.

    Uses Rich library for styled console output and input prompts.
    """

    def __init__(
        self,
        console: Console | None = None,
        *,
        allow_empty: bool = False,
        max_retries: int = 3,
    ):
        """Initialize with optional custom console and validation settings.

        Args:
            console: Rich Console instance (creates default if None)
            allow_empty: Whether to allow empty responses (default False)
            max_retries: Max retries for empty response when not allowed
        """
        self.console = console or Console()
        self.allow_empty = allow_empty
        self.max_retries = max_retries

    def ask(self, question: str) -> str:
        """Display question and get validated user input from console.

        Args:
            question: The question to display

        Returns:
            User's typed response
        """
        logger.debug("HITL question: %s", question)

        # Match permissions.py formatting for consistent UX
        self.console.print("\n[bold yellow]🤔 Clarification needed:[/bold yellow]")
        self.console.print(f"  {question}\n")
        speak("questions")  # Use same audio cue as permissions.py

        retries = 0
        while True:
            response = Prompt.ask("[bold green]Your answer[/bold green]")

            if response.strip() or self.allow_empty:
                break

            retries += 1
            if retries >= self.max_retries:
                logger.warning("Max retries reached, returning empty response")
                response = "[No response after retries]"
                break

            self.console.print("[yellow]Please provide a non-empty response.[/yellow]")

        logger.debug(
            "HITL response: %s", response[:50] if len(response) > 50 else response
        )
        return response


def create_ask_user_question_tool(provider: HumanInputProvider):
    """Create a DSPy-compatible ask_user_question tool.

    Factory function that wraps a HumanInputProvider into a callable
    that can be used as a DSPy ReAct tool.

    Args:
        provider: Any object implementing HumanInputProvider protocol

    Returns:
        A callable function suitable for use as a DSPy tool
    """

    def ask_user_question(question: str) -> str:
        """Ask user for clarification.

        Use this tool when:
        - The objective is ambiguous or unclear
        - You need to confirm assumptions before proceeding
        - Multiple valid interpretations exist
        - Critical decisions require human approval

        Args:
            question: Clear, specific question for the user

        Returns:
            User's response
        """
        return provider.ask(question)

    return ask_user_question
