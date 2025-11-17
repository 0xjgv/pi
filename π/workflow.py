from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import (
    HookMatcher,
)

from π.agent import run_agent
from π.hooks import check_bash_command, check_file_format
from π.utils import (
    create_workflow_dir,
    generate_workflow_id,
)


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

    print("=" * 80)
    print(f"Workflow ID: {workflow_id}")
    print(f"Thoughts: {workflow_thoughts_dir}")
    print(f"Logs: {workflow_log_dir}")
    print("=" * 80)

    # User query
    user_query = prompt.strip()

    # 1. Research codebase
    print("\n🔍 Stage 1/4: Researching codebase...")
    research_prompt_template, research_model = load_prompt("research_codebase")
    research_prompt = research_prompt_template.format(
        workflow_id=workflow_id,
        user_query=user_query,
    )
    research_codebase_result, research_stats = await run_agent(
        options=_get_options(cwd=cwd, model=research_model),
        log_file=workflow_log_dir / "research.log",
        prompt=f"{research_prompt}",
        verbose=False,
    )
    research_document = find_file_starting_with(
        base_dir=workflow_thoughts_dir,
        start_text="research",
    )
    print(f"✓ Research completed → {research_document.name}")
    print(f"  📊 {research_stats.get_summary()}")

    # 2. Create plan
    print("\n📝 Stage 2/4: Creating implementation plan...")
    plan_prompt_template, plan_model = load_prompt("create_plan")
    plan_prompt = plan_prompt_template.format(
        research_document=research_document,
        workflow_id=workflow_id,
        user_query=user_query,
    )
    create_plan_result, plan_stats = await run_agent(
        prompt=f"{plan_prompt}\n\n{research_codebase_result}",
        options=_get_options(cwd=cwd, model=plan_model),
        log_file=workflow_log_dir / "plan.log",
        verbose=False,
    )
    plan_document = find_file_starting_with(
        base_dir=workflow_thoughts_dir,
        start_text="plan",
    )
    print(f"✓ Plan created → {plan_document.name}")
    print(f"  📊 {plan_stats.get_summary()}")

    # 3. Review plan
    print("\n🔎 Stage 3/4: Reviewing plan...")
    review_prompt_template, review_model = load_prompt("review_plan")
    review_prompt = review_prompt_template.format(
        research_document=research_document,
        plan_document=plan_document,
        workflow_id=workflow_id,
        user_query=user_query,
    )
    review_plan_result, review_stats = await run_agent(
        prompt=f"{review_prompt}\n\n{create_plan_result}",
        options=_get_options(cwd=cwd, model=review_model),
        log_file=workflow_log_dir / "review.log",
        verbose=False,
    )
    print("✓ Plan reviewed")
    print(f"  📊 {review_stats.get_summary()}")

    # 4. Iterate plan (optional)
    print("\n🔄 Stage 4/4: Iterating on plan...")
    iterate_prompt_template, iterate_model = load_prompt("iterate_plan")
    iterate_prompt = iterate_prompt_template.format(
        research_document=research_document,
        plan_document=plan_document,
        workflow_id=workflow_id,
        user_query=user_query,
    )
    iterate_plan_result, iterate_stats = await run_agent(
        prompt=f"{iterate_prompt}\n\n{review_plan_result}",
        options=_get_options(cwd=cwd, model=iterate_model),
        log_file=workflow_log_dir / "iterate.log",
        verbose=False,
    )
    print("✓ Plan iteration completed")
    print(f"  📊 {iterate_stats.get_summary()}")

    # Calculate total stats
    total_tools = (
        research_stats.total_tools
        + plan_stats.total_tools
        + review_stats.total_tools
        + iterate_stats.total_tools
    )
    total_errors = (
        research_stats.errors
        + plan_stats.errors
        + review_stats.errors
        + iterate_stats.errors
    )

    print("\n" + "=" * 80)
    print("✅ Workflow completed successfully!")
    print(f"Final plan: {plan_document}")
    print(f"Full logs: {workflow_log_dir}")
    print(f"Total: {total_tools} tools executed, {total_errors} errors")
    print("=" * 80)

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
    return iterate_plan_result  # Return just the string result, not the stats
