"""Claude SDK session wrapper for isolated command execution."""

from __future__ import annotations

from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock


class ClaudeSession:
    """Run commands in isolated SDK sessions."""

    def __init__(self, *, working_dir: Path | None = None) -> None:
        self.working_dir = working_dir or Path.cwd()

    async def run_command(self, command: str, context: str = "") -> str:
        """Run a slash command and return the raw output.

        Args:
            command: The slash command (e.g., "/1_research_codebase")
            context: Additional context to provide

        Returns:
            The text result from the command execution
        """
        prompt = f"{command}\n\n{context}" if context else command
        result_content = ""
        result_parts = []

        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            cwd=self.working_dir,
            setting_sources=["project"],  # Load commands from current project
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt, session_id="default")

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    if message.result:
                        result_content = message.result
                    break
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_parts.append(block.text)

        return result_content if result_content else "\n".join(result_parts)
