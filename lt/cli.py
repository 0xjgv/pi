import asyncio
import logging
from pathlib import Path
from sys import argv
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    HookContext,
    HookJSONOutput,
    HookMatcher,
)

from lt.display import display_message

logger = logging.getLogger(__name__)


async def check_bash_command(
    input_data: dict[str, Any], _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """Prevent certain bash commands from being executed."""
    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]
    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")
    block_patterns = ["rm", "rm -rf", "rm -rf *", "rm -rf **/*"]

    for pattern in block_patterns:
        if command.startswith(pattern) or pattern in command:
            logger.warning(f"[LT-CLI] Blocked command: {command}")
            return {
                "hookSpecificOutput": {
                    "permissionDecisionReason": f"Command contains invalid pattern: {pattern}",
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                }
            }

    return {}


async def run():
    options = ClaudeAgentOptions(
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        setting_sources=["user", "project"],
        permission_mode="acceptEdits",
        cwd=Path(__file__).parent,
    )

    if len(argv) < 2:
        print("Usage: lt <prompt>")
        return

    prompt = argv[1]

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            display_message(msg)


def main():
    asyncio.run(run())
