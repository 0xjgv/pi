from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.hooks import (
    check_bash_command,
    check_file_format,
)
from π.permissions import can_use_tool

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
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
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
