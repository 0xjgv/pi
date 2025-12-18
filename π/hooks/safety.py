"""Safety checks for blocking dangerous operations."""

import re
from typing import cast

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

from π.hooks.logging import log_event


def is_dangerous_command(cmd: str) -> bool:
    """Check if a bash command is potentially dangerous.

    Args:
        cmd: The bash command string to check

    Returns:
        True if the command matches a dangerous pattern
    """
    dangerous_patterns = [
        (r"rm\s+-rf\s+(/|~)", "Dangerous rm -rf command detected!"),
        (r"(curl|wget).*\|.*sh", "Piping curl/wget to shell is not allowed!"),
        (r"dd\s+if=.*of=/dev/", "Direct disk write operation detected!"),
        (r"mkfs\.\w+", "File system formatting command detected!"),
        (r"fdisk\s+/dev/", "Disk partitioning command detected!"),
        (r">\s*/dev/sd[a-z]", "Direct write to disk device detected!"),
    ]

    for pattern, _ in dangerous_patterns:
        if re.search(pattern, cmd):
            return True

    simple_patterns = ["format c:", "rm -rf *"]
    return any(pattern in cmd.lower() for pattern in simple_patterns)


async def check_bash_command(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """PreToolUse hook: Block dangerous bash commands before execution.

    Trigger: Fires before Bash tool executes

    Blocked patterns (regex-based):
        - rm -rf / or ~
        - curl/wget piped to shell
        - dd writing to /dev/
        - mkfs commands
        - fdisk commands
        - Direct writes to /dev/sd*
        - rm -rf *
        - format c:
    """
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]
    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")

    if is_dangerous_command(command):
        print(f"🚫 Blocked dangerous command: {command}")
        log_event(
            "[BLOCKED_COMMAND]",
            {
                "command": command,
                "reason": "Dangerous pattern detected",
            },
        )
        return cast(
            HookJSONOutput,
            {
                "hookSpecificOutput": {
                    "permissionDecisionReason": "Command blocked: Potentially dangerous operation",
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                }
            },
        )

    return {}
