import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
)
from claude_agent_sdk.types import (
    HookMatcher,
)

from π.hooks import (
    check_bash_command,
    check_file_format,
    check_file_write,
    check_stage_output,
)
from π.utils import (
    create_workflow_dir,
    escape_csv_text,
    extract_message_content,
    extract_questions,
    generate_workflow_id,
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

SUPERVISOR_QUESTION_PROMPT = """You are the tech lead supervising an automated workflow.

**Workflow Objective**: {objective}

**Current Stage**: {stage}

**Stage Context**:
{context}

**Questions from the software engineer**:
{questions}

Provide clear, actionable answers based on:
1. Best practices for this codebase
2. The workflow objective
3. Technical feasibility

Be decisive. If you cannot answer definitively, provide your best recommendation with rationale.
Do NOT ask follow-up questions - make decisions and move forward.
"""

SUPERVISOR_REVIEW_PROMPT = """You are the tech lead reviewing stage output.

**Workflow Objective**: {objective}

**Stage Completed**: {stage}

**Output File**: {output_file}

Review the output and determine if it meets the objective requirements.

Respond with either:
- "APPROVED: [brief rationale]" - if the output is satisfactory
- "REVISION NEEDED: [specific feedback]" - if changes are required

Be constructive but decisive. The workflow cannot proceed without your approval.
"""

# Stage definitions: (command_name, expected_output_pattern, requires_review)
WORKFLOW_STAGES = [
    ("1_research_codebase", "thoughts/shared/research/", True),
    ("2_create_plan", "thoughts/shared/plans/", True),
    ("5_implement_plan", None, True),  # No file output, review via response
    ("7_validate_plan", None, False),  # Final validation, no review needed
]


class QueueMessage:
    def __init__(self, *, message_from: str, message: str):
        self.message_from = message_from
        self.message = message


class AgentQueue(asyncio.Queue[QueueMessage | None]):
    def __init__(self, name: str):
        self.name = name
        super().__init__()


@dataclass
class StageResult:
    """Captures the outcome of a stage execution."""

    stage: str
    status: Literal["complete", "questions", "error"]
    output_file: str | None = None
    questions: list[str] = field(default_factory=list)
    response: str | None = None


def capture_conversation_to_csv(
    *,
    workflow_dir: Path,
) -> Callable[[QueueMessage, str], None]:
    """Create a function to write conversation messages to a CSV file."""
    # Write the header once when the function is first called
    csv_file = workflow_dir / "conversation.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("message_from,message_to,message\n")

    # Return a function that can be called to append messages to the CSV file
    def _write_message(msg: QueueMessage, message_to: str) -> None:
        with open(csv_file, "a", encoding="utf-8") as f:
            f.write(f"{msg.message_from},{message_to},{escape_csv_text(msg.message)}\n")

    return _write_message


def get_agent_options(
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    cwd: Path = Path.cwd(),
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|MultiEdit|Edit", hooks=[check_file_format]),
                HookMatcher(
                    matcher="Write", hooks=[check_file_write, check_stage_output]
                ),
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        system_prompt=system_prompt,
        setting_sources=["project"],
        model=model,
        cwd=cwd,  # helps to find the project .claude dir
    )


async def query_agent(
    *,
    client: ClaudeSDKClient,
    prompt: str,
    name: str,
) -> str | None:
    await client.query(prompt=prompt)

    last_instance_label = None
    messages: list[str] = []

    async for msg in client.receive_response():
        instance_label = type(msg).__name__

        if last_instance_label is None or last_instance_label != instance_label:
            print(f"[{name}] MESSAGE:", instance_label)
            last_instance_label = instance_label

        content = extract_message_content(msg)
        if content is not None and content.strip() != "":
            messages.append(content)

    return messages[-1] if len(messages) > 0 else None


async def query_supervisor(
    *,
    client: ClaudeSDKClient,
    objective: str,
    stage: str,
    context: str,
    questions: list[str] | None = None,
    output_file: str | None = None,
) -> tuple[str, bool]:
    """Query supervisor for answers or approval.

    Returns:
        tuple of (response_text, is_approved)
        - For questions: (answers, True) - always approved to continue
        - For review: (feedback, True/False) - approved or needs revision
    """
    if questions:
        prompt = SUPERVISOR_QUESTION_PROMPT.format(
            objective=objective,
            stage=stage,
            context=context,
            questions="\n".join(f"- {q}" for q in questions),
        )
    else:
        prompt = SUPERVISOR_REVIEW_PROMPT.format(
            objective=objective,
            stage=stage,
            output_file=output_file,
        )

    response = await query_agent(client=client, prompt=prompt, name="supervisor")

    if questions:
        return response or "", True

    # Parse review response - strip markdown formatting like **APPROVED:**
    clean_response = response.strip().lstrip("*").strip().upper() if response else ""
    is_approved = clean_response.startswith("APPROVED")
    return response or "", is_approved


async def execute_stage(
    *,
    client: ClaudeSDKClient,
    stage_command: str,
    objective: str,
    supervisor_context: str,
) -> StageResult:
    """Execute a single stage and return the result."""
    # Build the stage prompt with objective and any supervisor context
    if supervisor_context:
        prompt = f"/{stage_command} {objective}\n\nContext from tech lead:\n{supervisor_context}"
    else:
        prompt = f"/{stage_command} {objective}"

    response = await query_agent(client=client, prompt=prompt, name="swe")

    if response is None:
        return StageResult(
            stage=stage_command,
            status="error",
            response="No response from agent",
        )

    # Check for questions in response
    questions = extract_questions(response)
    if questions:
        return StageResult(
            stage=stage_command,
            status="questions",
            questions=questions,
            response=response,
        )

    # Stage completed (file detection happens via hooks, but we mark complete here)
    return StageResult(
        stage=stage_command,
        status="complete",
        response=response,
    )


async def stage_controller(
    *,
    write_conversation: Callable[[QueueMessage, str], None] | None = None,
    supervisor_client: ClaudeSDKClient,
    swe_client: ClaudeSDKClient,
    objective: str,
) -> bool:
    """Orchestrate the staged workflow.

    Returns:
        True if workflow completed successfully, False otherwise.
    """
    stage_context = ""  # Accumulates supervisor feedback

    for stage_command, output_pattern, requires_review in WORKFLOW_STAGES:
        print(f"\n{'=' * 60}")
        print(f"[π-CLI] Starting stage: {stage_command}")
        print(f"{'=' * 60}\n")

        stage_complete = False
        max_iterations = 5  # Prevent infinite loops
        iterations = 0

        while not stage_complete and iterations < max_iterations:
            iterations += 1

            # Execute stage
            result = await execute_stage(
                client=swe_client,
                stage_command=stage_command,
                objective=objective,
                supervisor_context=stage_context,
            )

            if write_conversation and result.response:
                msg = QueueMessage(message_from="swe", message=result.response)
                write_conversation(msg, "stage_controller")

            if result.status == "error":
                print(f"[π-CLI] Stage {stage_command} failed: {result.response}")
                return False

            if result.status == "questions":
                # Escalate to supervisor
                print(
                    f"[π-CLI] Escalating {len(result.questions)} questions to supervisor"
                )

                answers, _ = await query_supervisor(
                    client=supervisor_client,
                    objective=objective,
                    stage=stage_command,
                    context=stage_context,
                    questions=result.questions,
                )

                if write_conversation:
                    msg = QueueMessage(message_from="supervisor", message=answers)
                    write_conversation(msg, "swe")

                # Add answers to context for next iteration
                stage_context = f"Previous questions and answers:\n{answers}"
                continue

            # Stage completed
            if requires_review:
                print("[π-CLI] Requesting supervisor review")

                feedback, is_approved = await query_supervisor(
                    client=supervisor_client,
                    objective=objective,
                    stage=stage_command,
                    context=stage_context,
                    output_file=result.output_file,
                )

                if write_conversation:
                    msg = QueueMessage(message_from="supervisor", message=feedback)
                    write_conversation(msg, "swe")

                if is_approved:
                    print(f"[π-CLI] Stage {stage_command} approved")
                    stage_context = f"Approved stage output: {result.output_file or 'implementation complete'}"
                    stage_complete = True
                else:
                    print(f"[π-CLI] Revision requested for {stage_command}")
                    stage_context = f"Revision feedback:\n{feedback}"
            else:
                stage_complete = True

        if not stage_complete:
            print(
                f"[π-CLI] Stage {stage_command} failed after {max_iterations} iterations"
            )
            return False

    print(f"\n{'=' * 60}")
    print("[π-CLI] Workflow completed successfully!")
    print(f"{'=' * 60}\n")
    return True


async def main(objective: str | None = None):
    """Run the staged workflow with supervisor oversight.

    Args:
        objective: The workflow objective. If None, prompts user.
    """
    if not objective:
        objective = input("Enter workflow objective: ").strip()
        if not objective:
            print("No objective provided. Exiting.")
            return

    print("\n[π-CLI] Starting workflow with objective:")
    print(f"  {objective}\n")

    # Set up workflow directory for conversation logging
    workflow_id = generate_workflow_id()
    workflow_dir = create_workflow_dir(Path.cwd() / ".logs", workflow_id)
    write_conversation = capture_conversation_to_csv(workflow_dir=workflow_dir)

    print(f"[π-CLI] Logging to: {workflow_dir}")

    # Create agent options
    swe_options = get_agent_options(
        system_prompt="You are a software engineer. Follow the workflow stages precisely.",
    )
    supervisor_options = get_agent_options(
        system_prompt="You are the tech lead. Review work, answer questions, and approve progress.",
        model="opus",  # Use more capable model for supervision
    )

    # Run the workflow
    async with (
        ClaudeSDKClient(options=supervisor_options) as supervisor_client,
        ClaudeSDKClient(options=swe_options) as swe_client,
    ):
        success = await stage_controller(
            write_conversation=write_conversation,
            supervisor_client=supervisor_client,
            swe_client=swe_client,
            objective=objective,
        )

        if success:
            print(f"\n[π-CLI] Workflow completed. Logs at: {workflow_dir}")
        else:
            print(f"\n[π-CLI] Workflow failed. Check logs at: {workflow_dir}")


if __name__ == "__main__":
    import sys

    objective = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    asyncio.run(main(objective))
