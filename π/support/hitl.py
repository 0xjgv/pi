"""Question answering providers for π workflow.

Provides a protocol and implementations for answering questions from workflow
agents using autonomous (agent-based) mode.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Protocol

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage

from π.support.directory import get_project_root
from π.workflow.context import get_ctx, get_event_loop

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

# Read-only tools for the answerer agent
_ANSWERER_TOOLS = ["Read", "Glob", "Grep"]


class QuestionAnswerer(Protocol):
    """Protocol for question answering providers.

    Implement this protocol to create custom answerers for different
    interfaces (agent, CLI, web, Slack, etc.).
    """

    def ask(self, questions: list[str]) -> list[str]:
        """Answer one or more questions.

        Args:
            questions: List of questions to answer

        Returns:
            List of answers (same order as questions)
        """
        ...


class AgentQuestionAnswerer:
    """Agent-based question answerer with codebase access.

    Uses Claude SDK with read-only tools (Read, Glob, Grep) to explore
    the codebase and answer questions autonomously.
    """

    def __init__(self, *, cwd: Path | None = None) -> None:
        """Initialize with optional working directory.

        Args:
            cwd: Working directory for codebase access (default: project root)
        """
        self.cwd = cwd
        self._answer_log: list[tuple[list[str], list[str]]] = []

    def _get_agent_options(self) -> ClaudeAgentOptions:
        """Get agent options with read-only tool subset."""
        cwd = self.cwd or get_project_root()
        return ClaudeAgentOptions(
            allowed_tools=_ANSWERER_TOOLS,
            permission_mode="acceptEdits",
            cwd=cwd,
        )

    def ask(self, questions: list[str]) -> list[str]:
        """Answer questions using Claude agent with codebase access.

        Args:
            questions: List of questions from the workflow agent

        Returns:
            List of answers (same length as questions)
        """
        logger.debug("AgentQuestionAnswerer: %d questions", len(questions))

        ctx = get_ctx()

        # Build context from workflow state
        context_parts = self._build_context(ctx)

        # Format questions for the agent
        questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))

        prompt = self._build_prompt(context_parts, questions_text, len(questions))

        # Execute via async bridge
        answers = self._execute_agent(prompt, len(questions))

        self._answer_log.append((questions.copy(), answers.copy()))
        return answers

    def _build_context(self, ctx: object) -> list[str]:
        """Build context parts from execution context."""
        parts = []
        if hasattr(ctx, "objective") and ctx.objective:
            parts.append(f"## Objective\n{ctx.objective}")
        if hasattr(ctx, "current_stage") and ctx.current_stage:
            parts.append(f"## Current Stage\n{ctx.current_stage}")

        # Include document paths (agent can read them if needed)
        if hasattr(ctx, "extracted_paths"):
            for doc_type, doc_paths in ctx.extracted_paths.items():
                if doc_paths:
                    paths_str = "\n".join(f"- {p}" for p in doc_paths)
                    parts.append(f"## {doc_type.title()} Documents\n{paths_str}")

        return parts

    def _build_prompt(
        self,
        context_parts: list[str],
        questions_text: str,
        count: int,
    ) -> str:
        """Build the agent prompt."""
        context = "\n\n".join(context_parts) if context_parts else "(no context)"

        return (
            "You are answering questions from another agent "
            "working on a codebase task.\n\n"
            f"## Workflow Context\n{context}\n\n"
            f"## Questions to Answer\n{questions_text}\n\n"
            "## Instructions\n"
            "1. Use Read, Glob, and Grep tools to explore the codebase as needed\n"
            "2. Answer each question based on codebase evidence\n"
            "3. Format your response as a numbered list matching the questions\n"
            "4. Be concise but complete\n\n"
            f"Respond with exactly {count} answer(s), one per line, "
            "numbered to match the questions."
        )

    def _execute_agent(self, prompt: str, expected_count: int) -> list[str]:
        """Execute Claude agent and parse answers."""

        async def _run() -> str:
            async with ClaudeSDKClient(options=self._get_agent_options()) as client:
                await client.query(prompt)

                result_text = ""
                async for message in client.receive_response():
                    if isinstance(message, ResultMessage):
                        result_text = message.result or ""
                        break

                return result_text

        # Get or create event loop
        loop = get_event_loop()
        result = loop.run_until_complete(_run())

        return self._parse_answers(result, expected_count)

    def _parse_answers(self, result: str, expected_count: int) -> list[str]:
        """Parse numbered answers from agent response."""
        lines = result.strip().split("\n")
        answers = []

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            # Match "1. answer" or "1) answer" or "1: answer" patterns
            match = re.match(r"^\d+[.):\s]+(.+)$", stripped)
            if match:
                answers.append(match.group(1).strip())
            elif stripped.startswith("-"):
                # Handle bullet point format
                answers.append(stripped[1:].strip())

        # Pad with placeholder if fewer answers than expected
        while len(answers) < expected_count:
            answers.append("(no answer)")

        return answers[:expected_count]

    @property
    def answers(self) -> list[tuple[list[str], list[str]]]:
        """Get log of all question/answer batches for debugging."""
        return self._answer_log.copy()


def create_ask_questions_tool(
    default_answerer: QuestionAnswerer | None = None,
) -> Callable[[list[str]], list[str]]:
    """Create a DSPy-compatible ask_questions tool.

    Factory function that creates a callable that:
    1. Checks ExecutionContext for a configured answerer
    2. Falls back to the default_answerer if not set
    3. Falls back to AgentQuestionAnswerer if no default

    Args:
        default_answerer: Fallback answerer when context has none

    Returns:
        A callable function suitable for use as a DSPy tool
    """
    fallback = default_answerer or AgentQuestionAnswerer()

    def ask_questions(questions: list[str]) -> list[str]:
        """Ask questions and get answers from codebase-aware agent.

        Use this tool when:
        - The objective is ambiguous or unclear
        - You need to clarify assumptions before proceeding
        - Multiple valid interpretations exist
        - You need information from the codebase to decide

        Args:
            questions: List of clear, specific questions

        Returns:
            List of answers (same length as questions)
        """
        ctx = get_ctx()
        answerer = ctx.input_provider or fallback
        return answerer.ask(questions)

    return ask_questions
