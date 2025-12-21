"""Human-in-the-loop (HITL) providers for π workflow."""

from typing import Protocol

from rich.console import Console
from rich.prompt import Prompt


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
    """Console-based human input provider for CLI applications.

    Uses Rich library for styled console output and input prompts.
    """

    def __init__(self, console: Console | None = None):
        """Initialize with optional custom console.

        Args:
            console: Rich Console instance (creates default if None)
        """
        self.console = console or Console()

    def ask(self, question: str) -> str:
        """Display question and get user input from console.

        Args:
            question: The question to display

        Returns:
            User's typed response
        """
        self.console.print("\n[bold yellow]Clarification needed:[/bold yellow]")
        self.console.print(f"  {question}\n")
        return Prompt.ask("[bold green]Your answer[/bold green]")


def create_ask_human_tool(provider: HumanInputProvider):
    """Create a DSPy-compatible ask_human tool.

    Factory function that wraps a HumanInputProvider into a callable
    that can be used as a DSPy ReAct tool.

    Args:
        provider: Any object implementing HumanInputProvider protocol

    Returns:
        A callable function suitable for use as a DSPy tool
    """

    def ask_human(question: str) -> str:
        """Ask human for clarification.

        Use this tool when:
        - The objective is ambiguous or unclear
        - You need to confirm assumptions before proceeding
        - Multiple valid interpretations exist
        - Critical decisions require human approval

        Args:
            question: Clear, specific question for the human

        Returns:
            Human's response
        """
        return provider.ask(question)

    return ask_human
