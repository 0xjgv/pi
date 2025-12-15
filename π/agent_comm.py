import asyncio
import json
import re
from pathlib import Path
from sys import argv

from claude_agent_sdk import ClaudeSDKClient
from pydantic import BaseModel

from π.agent import get_agent_options
from π.schemas import SupervisorDecision
from π.utils import (
    create_workflow_dir,
    extract_message_content,
    generate_workflow_id,
    log_workflow_event,
)
from π.workflow_mcp import WorkflowState, set_workflow_context

SWE_SYSTEM_PROMPT = """You are a software engineer executing workflow stages.

You have access to workflow control tools:
- **mcp__workflow__get_current_stage**: Get info about the current stage and requirements
- **mcp__workflow__complete_stage**: Signal when you've finished a stage
- **mcp__workflow__ask_supervisor**: Ask the tech lead when you need guidance

## Workflow Process:

1. Call `get_current_stage` to understand what you need to do
2. Execute the stage using the slash command (e.g., /1_research_codebase)
3. When finished, call `complete_stage` with:
   - stage: "research" | "plan" | "implement"
   - summary: Brief description of what you accomplished
   - output_file: Path to the file you created (required for research/plan stages)

4. If you have questions or are blocked, call `ask_supervisor` before proceeding

## Important:
- ALWAYS call `complete_stage` when you finish a stage
- ALWAYS provide the output_file for research and plan stages
- The workflow cannot proceed until you signal completion
"""

SUPERVISOR_SYSTEM_PROMPT = """You are the tech lead reviewing stage output and answering questions.

When reviewing or answering, provide clear, actionable guidance.
Be decisive - if uncertain, give your best recommendation with rationale.
Do NOT ask follow-up questions - make decisions and move forward.
"""

# Stage definitions: (command_name, stage_key)
WORKFLOW_STAGES = [
    ("1_research_codebase", "research"),
    ("2_create_plan", "plan"),
    ("3_implement_plan", "implement"),
]


def parse_structured_output(
    output_type: type[BaseModel],
    *,
    structured_output: dict | None = None,
    text_result: str | None = None,
) -> BaseModel | None:
    """Parse structured output from SDK or fallback to JSON text parsing."""
    if structured_output:
        try:
            return output_type.model_validate(structured_output)
        except ValueError:
            pass

    if text_result:
        text = text_result.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return output_type.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass

        try:
            data = json.loads(text)
            return output_type.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


async def run_stage(
    *,
    client: ClaudeSDKClient,
    command: str,
    context: str,
    workflow_dir: Path,
    workflow_state: WorkflowState,
) -> dict | None:
    """Execute a stage and wait for completion via MCP tool.

    The MCP `complete_stage` tool updates WorkflowState directly when called.
    We detect completion by checking if the state advanced.

    Returns:
        Dict with stage result if completed via tool, None if no completion signal.
    """
    prompt = f"/{command} {context}"
    print(f"[π-CLI] Executing: {prompt}")

    # Capture state before execution
    stage_before = workflow_state.current_stage
    index_before = workflow_state.current_stage_index

    await client.query(prompt=prompt)

    async for msg in client.receive_response():
        msg_type = type(msg).__name__

        # Log message for debugging
        content = extract_message_content(msg)
        if content:
            log_workflow_event(
                workflow_dir,
                "message",
                {"type": msg_type, "content_preview": content[:200] if content else None},
            )

    # Check if state advanced (complete_stage was called)
    if workflow_state.current_stage_index > index_before and stage_before:
        output_file = workflow_state.stage_outputs.get(stage_before)
        return {
            "stage_completed": stage_before,
            "output_file": output_file,
            "summary": f"Completed {stage_before} stage",
            "next_stage": workflow_state.current_stage,
            "workflow_complete": workflow_state.is_complete,
        }

    return None


async def run_workflow(
    *,
    supervisor_client: ClaudeSDKClient,
    swe_client: ClaudeSDKClient,
    workflow_state: WorkflowState,
    workflow_dir: Path,
) -> bool:
    """Execute the staged workflow with MCP tool-based state control.

    Returns:
        True if workflow completed successfully, False otherwise.
    """
    try:
        # Set workflow context for MCP tools
        set_workflow_context(workflow_state, supervisor_client)

        for stage_index, (command, stage_key) in enumerate(WORKFLOW_STAGES):
            print(
                f"\n[π-CLI] === Stage {stage_index + 1}/{len(WORKFLOW_STAGES)}: "
                f"/{command} ===\n"
            )
            log_workflow_event(
                workflow_dir,
                "stage_start",
                {"stage": stage_key, "index": stage_index}
            )

            # Execute stage - wait for completion tool call
            result = await run_stage(
                client=swe_client,
                command=command,
                context=workflow_state.context,
                workflow_dir=workflow_dir,
                workflow_state=workflow_state,
            )

            if result is None:
                print(f"[π-CLI] Stage {command} did not signal completion")
                log_workflow_event(
                    workflow_dir,
                    "stage_error",
                    {"stage": stage_key, "error": "no_completion_signal"},
                )
                return False

            if result.get("workflow_complete"):
                print("\n[π-CLI] === Workflow completed successfully ===")
                log_workflow_event(workflow_dir, "workflow_complete", {"success": True})
                return True

            print(f"[π-CLI] Stage {stage_key} completed: {result.get('summary', 'N/A')}")
            log_workflow_event(
                workflow_dir,
                "stage_complete",
                {
                    "stage": stage_key,
                    "output_file": result.get("output_file"),
                    "summary": result.get("summary"),
                },
            )

        print("\n[π-CLI] === Workflow completed successfully ===")
        log_workflow_event(workflow_dir, "workflow_complete", {"success": True})
        return True

    except Exception as e:
        print(f"[π-CLI] Workflow error: {e}")
        log_workflow_event(workflow_dir, "workflow_error", {"error": str(e)})
        return False


async def main(objective: str | None = None):
    """Run the staged workflow with MCP tool-based state control."""

    if not objective:
        objective = input("Enter workflow objective: ").strip()
        if not objective:
            print("No objective provided. Exiting.")
            return

    print("\n[π-CLI] Starting workflow with objective:")
    print(f"  {objective}\n")

    # Set up workflow
    workflow_id = generate_workflow_id()
    workflow_dir = create_workflow_dir(Path.cwd() / ".logs", workflow_id)
    workflow_state = WorkflowState(objective)

    print(f"[π-CLI] Logging to: {workflow_dir}")

    # Create agent options - SWE gets MCP tools
    swe_options = get_agent_options(
        system_prompt=SWE_SYSTEM_PROMPT,
        output_schema=None,
        model="haiku",
        include_workflow_mcp=True,
    )
    supervisor_options = get_agent_options(
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        output_schema=SupervisorDecision,
        model="haiku",
    )

    async with (
        ClaudeSDKClient(options=supervisor_options) as supervisor_client,
        ClaudeSDKClient(options=swe_options) as swe_client,
    ):
        success = await run_workflow(
            supervisor_client=supervisor_client,
            swe_client=swe_client,
            workflow_state=workflow_state,
            workflow_dir=workflow_dir,
        )

        if success:
            print("[π-CLI] Workflow completed successfully")
        else:
            print("[π-CLI] Workflow failed")


if __name__ == "__main__":
    objective = " ".join(argv[1:]) if len(argv) > 1 else None
    asyncio.run(main(objective))
