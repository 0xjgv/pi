"""Human-in-the-loop (HITL) providers for π workflow."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import dspy
from rich.console import Console
from rich.prompt import Prompt

from π.core import Provider, Tier, get_lm
from π.utils import speak
from π.workflow.context import get_ctx

if TYPE_CHECKING:
    from collections.abc import Callable

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
    ) -> None:
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


class AgentInputProvider:
    """Agent-based input provider for autonomous question answering.

    Reads workflow context from ExecutionContext and delegates
    questions to an LM for autonomous decision-making.
    """

    def __init__(self, lm: dspy.LM | None = None) -> None:
        """Initialize with optional language model.

        Args:
            lm: DSPy language model. If None, uses default from config.
        """
        self.lm = lm
        self._answer_log: list[tuple[str, str]] = []  # (question, answer) pairs

    def ask(self, question: str) -> str:
        """Generate an answer using LM with workflow context.

        Args:
            question: The question from the workflow agent

        Returns:
            LM-generated answer based on workflow context
        """
        logger.debug("AgentInputProvider question: %s", question)

        ctx = get_ctx()
        lm = self.lm or get_lm(Provider.Claude, Tier.HIGH)

        # Build context from workflow state
        context_parts = []
        if ctx.objective:
            context_parts.append(f"## Objective\n{ctx.objective}")
        if ctx.current_stage:
            context_parts.append(f"## Current Stage\n{ctx.current_stage}")

        # Include document contents if available
        for doc_type, doc_paths in ctx.extracted_paths.items():
            for doc_path in doc_paths:
                try:
                    content = Path(doc_path).read_text(encoding="utf-8")
                    if len(content) > 10000:
                        content = content[:10000] + "\n... (truncated)"
                    context_parts.append(f"## {doc_type.title()} Document\n{content}")
                except OSError:
                    logger.debug("Could not read %s document: %s", doc_type, doc_path)

        if context_parts:
            context = "\n\n".join(context_parts)
        else:
            context = "(no context available)"

        # Generate answer using DSPy
        with dspy.context(lm=lm):
            result = dspy.Predict("context: str, question: str -> answer: str")(
                context=context,
                question=question,
            )
            answer = result.answer

        truncated = answer[:100] if len(answer) > 100 else answer
        logger.info("AgentInputProvider answer: %s", truncated)
        self._answer_log.append((question, answer))

        return answer

    @property
    def answers(self) -> list[tuple[str, str]]:
        """Get log of all question/answer pairs for debugging."""
        return self._answer_log.copy()


def create_ask_user_question_tool(
    default_provider: HumanInputProvider | None = None,
) -> Callable[[str], str]:
    """Create a DSPy-compatible ask_user_question tool.

    Factory function that creates a callable that:
    1. Checks ExecutionContext for a configured provider
    2. Falls back to the default_provider if not set
    3. Falls back to ConsoleInputProvider if no default

    Args:
        default_provider: Fallback provider when context has none

    Returns:
        A callable function suitable for use as a DSPy tool
    """
    fallback = default_provider or ConsoleInputProvider()

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
            User's response (from human or agent depending on mode)
        """
        ctx = get_ctx()
        provider = ctx.input_provider or fallback
        return provider.ask(question)

    return ask_user_question
