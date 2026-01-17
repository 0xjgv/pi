"""π configuration - agent options and tool availability.

Core enums, models, and LM factory are in π.core (leaf module).
This module re-exports them for backwards compatibility.
"""

import os
from pathlib import Path
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.core import (
    STAGE_TIERS,
    TIER_TO_MODEL,
    Tier,
    WorkflowStage,
    get_lm,
)
from π.core.constants import WORKFLOW
from π.hooks import check_bash_command, check_file_format
from π.support import can_use_tool
from π.support.directory import get_project_root

# Workflow engine selection (dspy = existing DSPy ReAct, queue = new SDK queue-based)
WorkflowEngine = Literal["dspy", "queue"]
WORKFLOW_ENGINE: WorkflowEngine = os.environ.get("PI_WORKFLOW_ENGINE", "dspy")  # type: ignore[assignment]

# https://code.claude.com/docs/en/settings#tools-available-to-claude
AVAILABLE_TOOLS = [
    "AskUserQuestion",
    "Bash",
    "BashOutput",
    "Edit",
    "ExitPlanMode",
    "Glob",
    "Grep",
    "KillShell",
    "NotebookEdit",
    "Read",
    "Skill",
    "SlashCommand",
    "Task",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
]


def get_agent_options(
    *,
    system_prompt: str | None = None,
    cwd: Path | None = None,
) -> ClaudeAgentOptions:
    """Get Claude agent options with hooks and permissions configured."""
    cwd = cwd or get_project_root()
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[check_file_format]),
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        allowed_tools=AVAILABLE_TOOLS,
        system_prompt=system_prompt,
        setting_sources=["project"],
        can_use_tool=can_use_tool,
        cwd=cwd,
    )


__all__ = [
    "AVAILABLE_TOOLS",
    "STAGE_TIERS",
    "TIER_TO_MODEL",
    "WORKFLOW",
    "WORKFLOW_ENGINE",
    "Tier",
    "WorkflowEngine",
    "WorkflowStage",
    "get_agent_options",
    "get_lm",
]
