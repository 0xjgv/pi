from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.hooks import (
    check_bash_command,
    check_file_format,
)
from π.workflow_mcp import create_workflow_server

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
    include_workflow_mcp: bool = False,
    output_schema: type | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
    mcp_name = "workflow"
    workflow_server_config, workflow_tool_names = create_workflow_server(mcp_name)

    mcp_servers = {mcp_name: workflow_server_config} if include_workflow_mcp else {}
    AVAILABLE_TOOLS.extend(workflow_tool_names)

    options = ClaudeAgentOptions(
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
