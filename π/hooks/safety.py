"""Safety checks for blocking dangerous operations."""

import re

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

from π.console import console
from π.hooks.result import Block, HookResult, PassThrough, to_pre_hook_output


def is_dangerous_command(cmd: str) -> bool:
    """Check if a bash command is potentially dangerous.

    Args:
        cmd: The bash command string to check

    Returns:
        True if the command matches a dangerous pattern
    """
    # Strip common privilege escalation prefixes for pattern matching
    normalized_cmd = re.sub(r"^(sudo|doas|pkexec)\s+", "", cmd.strip())

    dangerous_patterns = [
        # Destructive file operations
        (r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*(/\s*$|/\s+|~\s*$|~\s+|\*)", "Dangerous rm"),
        # Piping remote content to shell
        (r"(curl|wget).*\|.*(ba)?sh", "Piping curl/wget to shell"),
        # Direct disk operations
        (r"dd\s+.*of=/dev/", "Direct disk write"),
        (r"mkfs\.\w+", "File system formatting"),
        (r"fdisk\s+/dev/", "Disk partitioning"),
        (r">\s*/dev/sd[a-z]", "Direct write to disk device"),
        # Fork bomb patterns
        (r":\(\)\s*\{.*:\|:.*\}", "Fork bomb"),
        (r"\..*\|.*&", "Potential fork bomb"),
        # Catastrophic permission/ownership on root
        (
            r"chmod\s+(-[a-zA-Z]*R[a-zA-Z]*\s+)*(777|a\+rwx)\s+/\s*$",
            "Recursive chmod 777 on root",
        ),
        (r"chown\s+(-[a-zA-Z]*R[a-zA-Z]*\s+)+\S+\s+/\s*$", "Recursive chown on root"),
        # File truncation of critical paths
        (r":>\s*/etc/", "Truncating /etc file"),
        (r"truncate\s+.*(/etc/|/var/|/usr/)", "Truncating system file"),
        # Overwriting critical system files
        (r">\s*/etc/(passwd|shadow|sudoers|hosts)", "Overwriting critical system file"),
    ]

    for pattern, _ in dangerous_patterns:
        if re.search(pattern, normalized_cmd):
            return True

    simple_patterns = ["format c:", "rm -rf *", ":(){ :|:& };:"]
    return any(pattern in cmd.lower() for pattern in simple_patterns)


def _check_bash_safety(tool_name: str | None, tool_input: dict) -> HookResult:
    """Check if bash command is safe to execute.

    Args:
        tool_name: Name of the tool that triggered the hook.
        tool_input: Input parameters from the tool.

    Returns:
        PassThrough if command is safe, Block if dangerous.
    """
    if tool_name != "Bash":
        return PassThrough(reason="not_bash_tool")

    command = tool_input.get("command", "")

    if is_dangerous_command(command):
        console.print(f"🚫 Blocked dangerous command: {command}")
        return Block(reason="Command blocked: Potentially dangerous operation")

    return PassThrough(reason="command_safe")


async def check_bash_command(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """PreToolUse hook: Block dangerous bash commands before execution.

    Trigger: Fires before Bash tool executes

    Blocked patterns (with sudo/doas/pkexec prefix handling):
        - rm -rf on / ~ or *
        - curl/wget piped to shell
        - dd/mkfs/fdisk disk operations
        - Direct writes to /dev/sd*
        - Fork bombs (:(){ :|:& };:)
        - chmod 777 / or chown -R on root
        - Truncation/overwrite of /etc files
    """
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]

    result = _check_bash_safety(tool_name, tool_input)
    return to_pre_hook_output(result)
