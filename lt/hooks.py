from typing import Any

from claude_agent_sdk.types import (
    HookContext,
    HookJSONOutput,
)


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
            print(f"[LT-CLI] Blocked command: {command}")
            return {
                "hookSpecificOutput": {
                    "permissionDecisionReason": f"Command contains invalid pattern: {pattern}",
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                }
            }

    return {}
