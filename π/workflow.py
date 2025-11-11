from pathlib import Path

from π.utils import (
    create_workflow_dir,
    generate_workflow_id,
    run_stage,
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

    user_query = prompt.strip()

    # 1. Research codebase
    print("\n🔍 Stage 1/7: Researching codebase...")
    exit_code, research_result = run_stage(
        stage_name="research",
        args=[workflow_id, user_query, str(workflow_log_dir), str(workflow_thoughts_dir)],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not research_result:
        print("❌ Research stage failed")
        return None
    research_document = research_result.document
    print(f"✓ Research completed → {Path(research_document).name if research_document else 'N/A'}")

    # 2. Create plan
    print("\n📝 Stage 2/7: Creating implementation plan...")
    exit_code, plan_result = run_stage(
        stage_name="plan",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            str(workflow_thoughts_dir),
            research_document or "",
            research_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not plan_result:
        print("❌ Plan stage failed")
        return None
    plan_document = plan_result.document
    print(f"✓ Plan created → {Path(plan_document).name if plan_document else 'N/A'}")

    # 3. Review plan
    print("\n🔎 Stage 3/7: Reviewing plan...")
    exit_code, review_result = run_stage(
        stage_name="review",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            research_document or "",
            plan_document or "",
            plan_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not review_result:
        print("❌ Review stage failed")
        return None
    print("✓ Plan reviewed")

    # 4. Iterate plan
    print("\n🔄 Stage 4/7: Iterating on plan...")
    exit_code, iterate_result = run_stage(
        stage_name="iterate",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            research_document or "",
            plan_document or "",
            review_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not iterate_result:
        print("❌ Iterate stage failed")
        return None
    print("✓ Plan iteration completed")

    # 5. Implement plan
    print("\n⚙️  Stage 5/7: Implementing plan...")
    exit_code, implement_result = run_stage(
        stage_name="implement",
        args=[
            workflow_id,
            str(workflow_log_dir),
            plan_document or "",
            iterate_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not implement_result:
        print("❌ Implementation stage failed")
        return None
    print("✓ Implementation completed")

    # 6. Commit changes
    print("\n💾 Stage 6/7: Committing changes...")
    exit_code, commit_result = run_stage(
        stage_name="commit",
        args=[
            workflow_id,
            str(workflow_log_dir),
            implement_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not commit_result:
        print("❌ Commit stage failed")
        return None
    print("✓ Changes committed")

    # 7. Validate plan
    print("\n✅ Stage 7/7: Validating implementation...")
    exit_code, validate_result = run_stage(
        stage_name="validate",
        args=[
            workflow_id,
            str(workflow_log_dir),
            plan_document or "",
            commit_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not validate_result:
        print("❌ Validation stage failed")
        return None
    print("✓ Validation completed")

    # Calculate total stats from all stages
    total_tools = sum([
        research_result.stats.get("total_tools", 0),
        plan_result.stats.get("total_tools", 0),
        review_result.stats.get("total_tools", 0),
        iterate_result.stats.get("total_tools", 0),
        implement_result.stats.get("total_tools", 0),
        commit_result.stats.get("total_tools", 0),
        validate_result.stats.get("total_tools", 0),
    ])
    total_errors = sum([
        research_result.stats.get("errors", 0),
        plan_result.stats.get("errors", 0),
        review_result.stats.get("errors", 0),
        iterate_result.stats.get("errors", 0),
        implement_result.stats.get("errors", 0),
        commit_result.stats.get("errors", 0),
        validate_result.stats.get("errors", 0),
    ])

    print("\n" + "=" * 80)
    print("✅ Workflow completed successfully!")
    print(f"Final plan: {plan_document}")
    print(f"Full logs: {workflow_log_dir}")
    print(f"Total: {total_tools} tools executed, {total_errors} errors")
    print("=" * 80)

    return validate_result.result
