"""Claude SDK session wrapper with π safety configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

from π.config import get_agent_options
from π.core.errors import AgentExecutionError

logger = logging.getLogger(__name__)


def _extract_text_blocks(message: AssistantMessage) -> list[str]:
    """Extract text from assistant message blocks."""
    return [block.text for block in message.content if isinstance(block, TextBlock)]


class ClaudeSession:
    """Run commands in isolated SDK sessions with safety hooks."""

    def __init__(self, *, working_dir: Path | None = None) -> None:
        """Initialize session.

        Args:
            working_dir: Working directory for SDK client. Defaults to cwd.
        """
        self.working_dir = working_dir or Path.cwd()

    async def run_command(
        self,
        command: str,
        context: str = "",
        *,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Run a slash command with safety hooks enabled.

        Args:
            command: The slash command (e.g., "/1_research_codebase")
            context: Additional context to provide
            session_id: Optional session ID for resumption

        Returns:
            Tuple of (text result, new session_id)

        Raises:
            AgentExecutionError: If execution fails
        """
        prompt = f"{command}\n\n{context}" if context else command
        options = get_agent_options(cwd=self.working_dir)

        logger.debug("Executing command: %s", command)

        try:
            result, new_session_id = await self._execute(prompt, options, session_id)
            logger.info("Completed: %d chars, session=%s", len(result), new_session_id)
            return result, new_session_id
        except Exception as e:
            logger.exception("Command execution failed")
            raise AgentExecutionError(f"'{command}' failed: {e}") from e

    async def _execute(
        self,
        prompt: str,
        options: ClaudeAgentOptions,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Execute command and collect response."""
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt, session_id=session_id or "default")

            result_parts: list[str] = []
            result_content = ""
            new_session_id = ""

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_content = message.result or ""
                    new_session_id = message.session_id
                    break
                if isinstance(message, AssistantMessage):
                    result_parts.extend(_extract_text_blocks(message))

            return result_content or "\n".join(result_parts), new_session_id
