"""Hook result types for explicit pass-through and block semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_agent_sdk.types import HookJSONOutput


@dataclass(frozen=True, slots=True)
class PassThrough:
    """Hook allows operation to proceed."""

    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Block:
    """Hook blocks operation."""

    reason: str


type HookResult = PassThrough | Block


def to_pre_hook_output(result: HookResult) -> HookJSONOutput:
    """Convert HookResult to PreToolUse hook output format.

    Args:
        result: PassThrough or Block result.

    Returns:
        Empty dict for pass-through, or deny decision for block.
    """
    if isinstance(result, PassThrough):
        return {}
    return {
        "hookSpecificOutput": {
            "permissionDecisionReason": result.reason,
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
        }
    }


def to_post_hook_output(result: HookResult, *, file_name: str = "") -> HookJSONOutput:
    """Convert HookResult to PostToolUse hook output format.

    Args:
        result: PassThrough or Block result.
        file_name: Name of file that failed checks (for error message).

    Returns:
        Empty dict for pass-through, or block decision for block.
    """
    if isinstance(result, PassThrough):
        return {}
    return {
        "decision": "block",
        "reason": result.reason or f"Code quality checks failed for {file_name}",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
        },
    }
