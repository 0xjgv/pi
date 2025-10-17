from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    HookMatcher,
)

from lt.display import display_message
from lt.hooks import check_bash_command


async def run_agent(*, prompt: str, cwd: Path) -> None:
    print(">>>", cwd)
    options = ClaudeAgentOptions(
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        setting_sources=["user", "project"],
        permission_mode="acceptEdits",
        cwd=cwd,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt=prompt)

        async for msg in client.receive_response():
            display_message(msg)
