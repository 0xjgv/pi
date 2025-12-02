from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.hooks import (
    check_bash_command,
    check_file_format,
)

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
]


def get_agent_options(
    *,
    output_schema: type | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
    options = ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format]),
                # HookMatcher(
                #     matcher="Write", hooks=[check_file_write, check_stage_output]
                # ),
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
        cwd=cwd,  # helps to find the project .claude dir
    )

    if output_schema:
        options.output_format = {
            "type": "json_schema",
            "json_schema": {
                "schema": output_schema.model_json_schema(),
                "name": output_schema.__name__,
            },
        }

    return options
