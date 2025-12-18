"""
Hook validation system for Claude Agent SDK tool execution.

This module implements pre- and post-execution validation hooks that:
- PreToolUse: Intercept tool calls before execution (blocks dangerous commands)
- PostToolUse: Validate tool outputs after execution (runs code quality checks)

Hooks return structured JSON responses following the Claude Agent SDK spec:
- Empty dict {} means "no action needed, proceed normally"
- HookJSONOutput with "decision": "block" blocks the operation
- HookJSONOutput with "permissionDecision": "deny" denies execution

Hook Flow:
  Tool called → PreToolUse hooks → Tool executes → PostToolUse hooks → Result

Public API:
    check_file_format: PostToolUse hook for code quality checks
    check_bash_command: PreToolUse hook for dangerous command blocking
"""

from pathlib import Path
from typing import cast

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

# Import checkers to register them in the registry
from π.hooks import checkers as _checkers  # noqa: F401
from π.hooks.logging import log_event
from π.hooks.registry import get_checker
from π.hooks.safety import check_bash_command
from π.hooks.utils import compact_path, console

# Re-export public API
__all__ = ["check_file_format", "check_bash_command"]


async def check_file_format(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """PostToolUse hook: Run language-specific linters after file modifications.

    Trigger: Fires after Edit or Write
    """
    tool_name = input_data.get("tool_name")

    # Only check files modified by Edit or Write tools
    if tool_name not in ("Edit", "Write"):
        return {}

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path")
    if not file_path:
        return {}

    path = Path(file_path)
    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    checker_info = get_checker(suffix)
    if checker_info:
        console.print(f"🔍 Checking {compact_path(path)} (triggered by {tool_name})")

        # Run the checker
        exit_code = checker_info.func(path, tool_name)

        # Log the check result
        log_event(
            "[LANGUAGE_CHECK]",
            {
                "result": "passed" if exit_code == 0 else "failed",
                "tool": tool_name or "unknown",
                "file": compact_path(path),
                "exit_code": exit_code,
                "checker": suffix,
            },
        )

        # If checks failed (exit code 2), block the operation
        if exit_code == 2:
            return cast(
                HookJSONOutput,
                {
                    "decision": "block",
                    "reason": f"Code quality checks failed for {path.name}",
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                    },
                },
            )

    return {}
