from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import (
    HookMatcher,
)

from π.agent import run_agent
from π.hooks import check_bash_command, check_file_format
from π.utils import create_workflow_dir, generate_workflow_id, load_prompt


def _get_options(*, cwd: Path, model: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format])
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        setting_sources=["project"],
        model=model,
        cwd=cwd,
    )


async def run_workflow(*, prompt: str, cwd: Path) -> None | str:
    # Generate unique workflow ID
    workflow_id = generate_workflow_id()

    # Create workflow-specific thoughts & log directories
    thoughts_base = cwd / Path("thoughts")
    logs_base = cwd / Path(".logs")

    workflow_thoughts_dir = create_workflow_dir(thoughts_base, workflow_id)
    workflow_log_dir = create_workflow_dir(logs_base, workflow_id)

    print(f"Thoughts directory: {workflow_thoughts_dir}\n")
    print(f"Logs directory: {workflow_log_dir}\n")
    print(f"Workflow ID: {workflow_id}")

    # User prompt
    user_prompt = prompt.strip()

    # Research codebase
    research_prompt_template, research_model = load_prompt("research_codebase")
    research_prompt = research_prompt_template.format(
        workflow_id=workflow_id,
        log_dir=workflow_log_dir,
    )
    research_codebase_result = await run_agent(
        options=_get_options(cwd=cwd, model=research_model),
        prompt=f"{research_prompt}\n\n{user_prompt}",
        log_file=workflow_log_dir / "research.log",
    )

    # Create plan
    plan_prompt_template, plan_model = load_prompt("create_plan")
    plan_prompt = plan_prompt_template.format(
        workflow_id=workflow_id,
        log_dir=workflow_log_dir,
    )
    create_plan_result = await run_agent(
        prompt=f"{plan_prompt}\n\n{research_codebase_result}",
        options=_get_options(cwd=cwd, model=plan_model),
        log_file=workflow_log_dir / "plan.log",
    )

    # Review plan
    review_prompt_template, review_model = load_prompt("review_plan")
    review_prompt = review_prompt_template.format(
        workflow_id=workflow_id,
        log_dir=workflow_log_dir,
    )
    review_plan_result = await run_agent(
        prompt=f"{review_prompt}\n\n{create_plan_result}",
        options=_get_options(cwd=cwd, model=review_model),
        log_file=workflow_log_dir / "review.log",
    )

    # Iterate plan
    iterate_prompt_template, iterate_model = load_prompt("iterate_plan")
    iterate_prompt = iterate_prompt_template.format(
        workflow_id=workflow_id,
        log_dir=workflow_log_dir,
    )

    iterate_plan_result = await run_agent(
        prompt=f"{iterate_prompt}\n\n{review_plan_result}",
        log_file=workflow_log_dir / "iterate.log",
        options=_get_options(cwd=cwd, model=iterate_model),
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
