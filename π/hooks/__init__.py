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

# Import checkers to register them in the registry
from π.hooks import checkers as _checkers
from π.hooks.linting import check_file_format
from π.hooks.safety import check_bash_command

# Re-export public API (include _checkers for side-effect registration)
__all__ = ["_checkers", "check_bash_command", "check_file_format"]
