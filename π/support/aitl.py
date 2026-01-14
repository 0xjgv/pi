"""Question answering providers for π workflow.

Provides a protocol and implementations for answering questions from workflow
agents using autonomous (agent-based) mode.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Protocol

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage
from pydantic import BaseModel

from π.support.directory import get_project_root
from π.workflow.context import ExecutionContext, get_ctx, get_event_loop

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


class Question(BaseModel):
    """A question with response format hint for AITL agent."""

    text: str
    response_type: Literal["brief", "detailed", "yes_no"] = "brief"
    context: str | None = None


class Answer(BaseModel):
    """Structured answer from AITL agent."""

    content: str
    evidence: str | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


def _normalize_questions(
    questions: list[Question] | list[str] | list[dict],
) -> list[Question]:
    """Normalize various question formats to list[Question].

    Supports:
    - list[Question]: Pass through (new format)
    - list[str]: Convert to Question(text=str) (legacy format)
    - list[dict]: Convert via Question(**dict) (dict format)

    Args:
        questions: Questions in any supported format

    Returns:
        Normalized list of Question objects
    """
    if not questions:
        return []

    first = questions[0]
    if isinstance(first, Question):
        return questions  # type: ignore[return-value]
    if isinstance(first, str):
        return [Question(text=q) for q in questions]  # type: ignore[arg-type]
    if isinstance(first, dict):
        return [Question(**q) for q in questions]  # type: ignore[arg-type]

    msg = f"Unsupported question format: {type(first)}"
    raise TypeError(msg)


# Read-only tools for the answerer agent
_ANSWERER_TOOLS = ["Read", "Glob", "Grep"]


class QuestionAnswerer(Protocol):
    """Protocol for question answering providers.

    Implement this protocol to create custom answerers for different
    interfaces (agent, CLI, web, Slack, etc.).
    """

    def ask(self, questions: list[Question]) -> list[str]:
        """Answer one or more questions.

        Args:
            questions: List of Question objects to answer

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

    def ask(self, questions: list[Question]) -> list[str]:
        """Answer questions using Claude agent with codebase access.

        Args:
            questions: List of Question objects from the workflow agent

        Returns:
            List of answers (same length as questions)
        """
        batch_id = uuid.uuid4().hex[:8]
        start_time = time.perf_counter()

        logger.debug(
            "AgentQuestionAnswerer: %d questions (batch=%s)", len(questions), batch_id
        )

        # Log questions at DEBUG level for verbose mode
        for i, q in enumerate(questions, 1):
            logger.debug("AITL Q%d: %s", i, q.text)

        # Build prompt with structured questions (context built internally)
        prompt = self._build_prompt(questions)

        # Execute via async bridge
        answers = self._execute_agent(prompt, len(questions))

        # Calculate duration
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Emit JSON line for programmatic analysis
        aitl_data = {
            "batch_id": batch_id,
            "timestamp": datetime.now().isoformat(),
            "count": len(questions),
            "questions": [q.model_dump() for q in questions],
            "answers": answers,
            "duration_ms": duration_ms,
        }
        logger.info("AITL_JSON: %s", json.dumps(aitl_data, ensure_ascii=False))

        for i, a in enumerate(answers, 1):
            logger.debug("AITL A%d: %s", i, a)

        self._answer_log.append(
            ([q.text for q in questions], answers.copy()),
        )
        return answers

    def _build_context(self, ctx: ExecutionContext) -> list[str]:
        """Build context parts from execution context."""
        parts = []
        if ctx.objective:
            parts.append(f"## Objective\n{ctx.objective}")
        if ctx.current_stage:
            parts.append(f"## Current Stage\n{ctx.current_stage}")

        # Include document paths (agent can read them if needed)
        for doc_type, doc_paths in ctx.extracted_paths.items():
            if doc_paths:
                paths_str = "\n".join(f"- {p}" for p in doc_paths)
                parts.append(f"## {doc_type.title()} Documents\n{paths_str}")

        return parts

    def _build_prompt(self, questions: list[Question]) -> str:
        """Build the agent prompt with structured question format."""
        ctx = get_ctx()
        context_parts = self._build_context(ctx)
        context = "\n\n".join(context_parts) if context_parts else "(no context)"

        # Format questions with delimiters and response hints
        response_hints = {
            "brief": "1-2 sentences with key evidence",
            "detailed": "Full analysis with file paths, reasoning, and trade-offs",
            "yes_no": "Yes or No, followed by brief explanation",
        }

        question_blocks = []
        for i, q in enumerate(questions, 1):
            hint = response_hints[q.response_type]
            block = f"=== QUESTION {i} ===\n{q.text}\n[Expected: {hint}]"
            if q.context:
                block += f"\n[Context: {q.context}]"
            question_blocks.append(block)

        questions_text = "\n\n".join(question_blocks)

        return f"""You are a senior technical advisor answering codebase questions.

## Workflow Context
{context}

## Questions
{questions_text}

## Response Format
You MUST respond with valid JSON in this exact structure:

```json
{{
  "answers": [
    {{
      "content": "Your answer here",
      "evidence": "file/path:line or null if none",
      "confidence": "HIGH or MEDIUM or LOW"
    }}
  ]
}}
```

Guidelines:
- Provide exactly {len(questions)} answer(s) in the "answers" array
- "content": The direct answer to the question
- "evidence": File paths with line numbers, or null if not applicable
- "confidence": HIGH (found code evidence), MEDIUM (inferred), LOW (uncertain)
- Use Read, Glob, Grep to find concrete evidence before answering
- If a question cannot be answered from code, say so in "content" with confidence LOW
"""

    def _execute_agent(self, prompt: str, expected_count: int) -> list[str]:
        """Execute Claude agent and parse answers."""

        async def _run() -> str:
            result_text = ""
            async with ClaudeSDKClient(options=self._get_agent_options()) as client:
                await client.query(prompt)
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
        """Parse answers from agent response.

        Attempts JSON extraction first, falls back to delimiter parsing.
        """
        # Attempt 1: JSON extraction
        answers = self._parse_json_answers(result, expected_count)
        if answers:
            return answers

        # Attempt 2: Delimiter-based parsing
        answers = self._parse_delimiter_answers(result, expected_count)
        if answers:
            return answers

        # Attempt 3: Legacy line-by-line parsing (backward compatibility)
        return self._parse_legacy_answers(result, expected_count)

    def _parse_json_answers(
        self,
        result: str,
        expected_count: int,
    ) -> list[str] | None:
        """Extract answers from JSON response."""
        # Try to find JSON block in markdown code fence
        json_match = re.search(r"```json\s*(.*?)\s*```", result, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r"\{.*\"answers\".*\}", result, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return None

        try:
            data = json.loads(json_str)
            if "answers" not in data:
                return None

            answers = []
            for item in data["answers"][:expected_count]:
                if isinstance(item, dict):
                    content = item.get("content", "(no content)")
                    evidence = item.get("evidence")
                    confidence = item.get("confidence", "MEDIUM")
                    # Format as single string with metadata
                    answer = content
                    if evidence:
                        answer += f" [evidence: {evidence}]"
                    answer += f" [confidence: {confidence}]"
                    answers.append(answer)
                else:
                    answers.append(str(item))

            # Pad if needed
            while len(answers) < expected_count:
                answers.append("(no answer)")

            return answers
        except json.JSONDecodeError:
            logger.debug("JSON parsing failed, falling back to delimiter parsing")
            return None

    def _parse_delimiter_answers(
        self,
        result: str,
        expected_count: int,
    ) -> list[str] | None:
        """Extract answers using delimiter markers."""
        pattern = r"===\s*ANSWER\s*(\d+)\s*===\s*(.*?)(?====\s*ANSWER|\Z)"
        matches = re.findall(pattern, result, re.DOTALL | re.IGNORECASE)

        if not matches:
            return None

        answer_map = {}
        for num_str, content in matches:
            num = int(num_str)
            answer_map[num] = content.strip()

        answers = []
        for i in range(1, expected_count + 1):
            answers.append(answer_map.get(i, "(no answer)"))

        return answers

    def _parse_legacy_answers(self, result: str, expected_count: int) -> list[str]:
        """Legacy line-by-line parsing for backward compatibility."""
        lines = result.strip().split("\n")
        answers = []

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            match = re.match(r"^\d+[.):\s]+(.+)$", stripped)
            if match:
                answers.append(match.group(1).strip())
            elif stripped.startswith("-"):
                answers.append(stripped[1:].strip())

        while len(answers) < expected_count:
            answers.append("(no answer)")

        return answers[:expected_count]

    @property
    def answers(self) -> list[tuple[list[str], list[str]]]:
        """Get log of all question/answer batches for debugging."""
        return self._answer_log.copy()


def create_ask_questions_tool(
    default_answerer: QuestionAnswerer | None = None,
) -> Callable[[list[Question]], list[str]]:
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

    def ask_questions(questions: list[Question]) -> list[str]:
        """Ask questions and get answers from codebase-aware agent.

        Use this tool when:
        - The objective is ambiguous or unclear
        - You need to clarify assumptions before proceeding
        - Multiple valid interpretations exist
        - You need information from the codebase to decide

        Args:
            questions: List of Question objects with fields:
                - text (str, required): The question to ask
                - response_type (str, optional): "brief", "detailed", or "yes_no"
                - context (str, optional): Additional context for this question

        Returns:
            List of answers (same length as questions)

        Example:
            ask_questions([
                Question(text="Does the project have CI/CD?", response_type="brief"),
                Question(text="What testing patterns exist?", response_type="detailed")
            ])
        """
        ctx = get_ctx()
        answerer = ctx.input_provider or fallback

        # Normalize input (handles legacy list[str] and dict formats)
        normalized = _normalize_questions(questions)
        return answerer.ask(normalized)

    return ask_questions
