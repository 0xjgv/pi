from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.hooks import (
    check_bash_command,
    check_file_format,
)
from π.workflow_mcp import create_workflow_server

ALLOWED_TOOLS = [
    "Task",
    "Bash",
    "Glob",
    "Grep",
    "ExitPlanMode",
    "Read",
    "Edit",
    "Write",
    "NotebookEdit",
    "WebFetch",
    "TodoWrite",
    "WebSearch",
    "BashOutput",
    "KillShell",
    "Skill",
    "SlashCommand",
    # MCP workflow tools
    "mcp__workflow__complete_stage",
    "mcp__workflow__ask_supervisor",
    "mcp__workflow__get_current_stage",
]


def get_agent_options(
    *,
    output_schema: type | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    cwd: Path = Path.cwd(),
    include_workflow_mcp: bool = False,
) -> ClaudeAgentOptions:
    mcp_servers = {"wf": create_workflow_server()} if include_workflow_mcp else {}

    options = ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format]),
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        allowed_tools=ALLOWED_TOOLS,
        system_prompt=system_prompt,
        setting_sources=["project"],
        model=model,
        cwd=cwd,
    )

    if mcp_servers:
        options.mcp_servers = mcp_servers  # type: ignore[assignment]

    if output_schema:
        options.output_format = {
            "type": "json_schema",
            "json_schema": {
                "schema": output_schema.model_json_schema(),
                "name": output_schema.__name__,
            },
        }

    return options
