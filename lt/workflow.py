from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import (
    HookMatcher,
)

from lt.agent import run_agent
from lt.hooks import check_bash_command
from lt.utils import create_workflow_log_dir, generate_workflow_id


def _get_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        setting_sources=["project"],
        cwd=cwd,
    )


async def run_workflow(*, prompt: str, cwd: Path) -> None | str:
    # Generate unique workflow ID
    workflow_id = generate_workflow_id()

    # Create workflow-specific log directory
    logs_base = cwd / Path(".logs")
    workflow_log_dir = create_workflow_log_dir(logs_base, workflow_id)

    print(f"Workflow ID: {workflow_id}")
    print(f"Logs directory: {workflow_log_dir}\n")

    # Agent options
    options = _get_options(cwd=cwd)
    prompt = prompt.strip()

    # Research codebase
    research_codebase_result = await run_agent(
        log_file=workflow_log_dir / "research.log",
        prompt=f"/research_codebase {prompt}",
        options=options,
    )

    # # Create plan
    create_plan_result = await run_agent(
        prompt=f"/create_plan {research_codebase_result}",
        log_file=workflow_log_dir / "plan.log",
        options=options,
    )

    # # Review plan
    review_plan_result = await run_agent(
        prompt=f"/review_plan {create_plan_result}",
        log_file=workflow_log_dir / "review.log",
        options=options,
    )

    # # Iterate plan
    iterate_plan_result = await run_agent(
        prompt=f"/iterate_plan {review_plan_result}",
        log_file=workflow_log_dir / "iterate.log",
        options=options,
    )

    # # Implement plan
    # implement_plan_result = await run_agent(
    #     prompt=f"/implement_plan {iterate_plan_result}",
    #     log_file=workflow_log_dir / "implement.log",
    #     options=options,
    # )

    # # Commit changes
    # Commit asks the user for input
    # commit_result = await run_agent(
    #     prompt=f"/commit {implement_plan_result}",
    #     options=options,
    #     log_file=workflow_log_dir / "commit.log",
    # )

    # # Validate plan
    # implement_plan_result = await run_agent(
    #     prompt=f"/validate_plan {implement_plan_result}",
    #     options=options,
    #     log_file=workflow_log_dir / "validate.log",
    # )

    # # Commit changes
    return iterate_plan_result
