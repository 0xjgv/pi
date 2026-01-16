"""PostToolUse hook for code quality checks after file modifications."""

from pathlib import Path

from claude_agent_sdk.types import HookContext, HookInput, HookJSONOutput

from π.console import console
from π.hooks.registry import get_checker
from π.hooks.result import Block, HookResult, PassThrough, to_post_hook_output
from π.hooks.utils import compact_path


def _check_edit(tool_name: str | None, tool_input: dict) -> HookResult:
    """Check if file modification passes quality checks.

    Args:
        tool_name: Name of the tool that triggered the hook.
        tool_input: Input parameters from the tool.

    Returns:
        PassThrough if checks pass or don't apply, Block if checks fail.
    """
    # Only check files modified by Edit or Write tools
    if tool_name not in ("Edit", "Write"):
        return PassThrough(reason="not_edit_operation")

    file_path = tool_input.get("file_path")
    if not file_path:
        return PassThrough(reason="no_file_path")

    path = Path(file_path)
    if not path.exists():
        return PassThrough(reason="file_not_found")

    suffix = path.suffix.lower()
    checker = get_checker(suffix)
    if not checker:
        return PassThrough(reason="no_checker_for_extension")

    console.print(f"🔍 Checking {compact_path(path)} (triggered by {tool_name})")

    # Run the checker
    exit_code = checker(path, tool_name)

    # If checks failed (exit code 2), block the operation
    if exit_code == 2:
        return Block(reason=f"Code quality checks failed for {path.name}")

    return PassThrough(reason="checks_passed")


async def check_file_format(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """PostToolUse hook: Run language-specific linters after file modifications.

    Trigger: Fires after Edit or Write
    """
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})

    result = _check_edit(tool_name, tool_input)
    return to_post_hook_output(result)
