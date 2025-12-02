import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, TypeVar

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
)
from claude_agent_sdk.types import (
    HookMatcher,
)
from pydantic import BaseModel

from π.hooks import (
    check_bash_command,
    check_file_format,
    check_file_write,
    check_stage_output,
)
from π.schemas import SupervisorDecision
from π.utils import (
    create_workflow_dir,
    escape_csv_text,
    extract_message_content,
    generate_workflow_id,
)

T = TypeVar("T", bound=BaseModel)

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

SWE_SYSTEM_PROMPT = """You are a software engineer executing workflow stages.

When you complete your task, you MUST respond with a JSON object:
- status: "complete" when done, "questions" if you need clarification, "error" if failed
- summary: Brief description of what you did
- output_file: Path to any file you created (or null)
- questions: List of specific questions (only when status is "questions")
- error_message: Error details (only when status is "error")

Example completion:
{"status": "complete", "summary": "Created research document analyzing auth flow", "output_file": "thoughts/shared/research/2025-12-02-auth-flow.md", "questions": [], "error_message": null}

Example questions:
{"status": "questions", "summary": "Analyzed codebase structure", "output_file": null, "questions": ["Should I focus on REST or GraphQL endpoints?", "Which authentication method should I document?"], "error_message": null}
"""

SUPERVISOR_SYSTEM_PROMPT = """You are the tech lead reviewing stage output and answering questions.

When reviewing or answering, you MUST respond with a JSON object:
- approved: true if work is satisfactory or questions are answered, false if revisions needed
- feedback: Your rationale, answers to questions, or specific revision instructions

Example approval:
{"approved": true, "feedback": "Research is comprehensive and covers all required areas."}

Example revision request:
{"approved": false, "feedback": "Missing analysis of error handling patterns. Please add a section on exception flow."}
"""

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
    output_schema: type | None = None,
) -> ClaudeAgentOptions:
    options = ClaudeAgentOptions(
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

    if output_schema:
        options.output_format = {
            "type": "json_schema",
            "json_schema": {
                "name": output_schema.__name__,
                "schema": output_schema.model_json_schema(),
            },
        }

    return options


def parse_structured_output(
    output_type: type[T],
    *,
    structured_output: dict | None = None,
    text_result: str | None = None,
) -> T | None:
    """Parse structured output from SDK or fallback to JSON text parsing.

    Args:
        output_type: Pydantic model class to validate against
        structured_output: SDK's structured_output attribute (if available)
        text_result: Raw text result to parse as JSON fallback

    Returns:
        Validated Pydantic model instance, or None if parsing fails
    """
    # First try SDK's structured_output
    if structured_output:
        try:
            return output_type.model_validate(structured_output)
        except ValueError:
            pass

    # Fallback: parse JSON from text
    if text_result:
        text = text_result.strip()

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return output_type.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Try parsing entire text as JSON
        try:
            data = json.loads(text)
            return output_type.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


async def query_agent(
    *,
    client: ClaudeSDKClient,
    prompt: str,
    name: str,
    output_type: type[T] | None = None,
) -> T | str | None:
    """Query agent and optionally parse structured output.

    Args:
        client: The SDK client
        prompt: Query prompt
        name: Agent name for logging
        output_type: If provided, parse structured_output into this Pydantic model

    Returns:
        Parsed model if output_type provided and structured_output available,
        otherwise last text message, or None if no response.
    """
    await client.query(prompt=prompt)

    last_instance_label = None
    messages: list[str] = []
    sdk_structured_output: dict | None = None

    async for msg in client.receive_response():
        instance_label = type(msg).__name__

        if last_instance_label is None or last_instance_label != instance_label:
            print(f"[{name}] MESSAGE:", instance_label)
            last_instance_label = instance_label

        # Capture SDK's structured_output if available
        if hasattr(msg, "structured_output") and msg.structured_output:
            sdk_structured_output = msg.structured_output

        content = extract_message_content(msg)
        if content is not None and content.strip() != "":
            messages.append(content)

    # Parse structured output (SDK first, then text fallback)
    if output_type:
        last_message = messages[-1] if messages else None
        result = parse_structured_output(
            output_type,
            structured_output=sdk_structured_output,
            text_result=last_message,
        )
        if result:
            return result

    return messages[-1] if messages else None


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
    """

    if questions:
        prompt = SUPERVISOR_QUESTION_PROMPT.format(
            questions="\n".join(f"- {q}" for q in questions),
            objective=objective,
            context=context,
            stage=stage,
        )
    else:
        prompt = SUPERVISOR_REVIEW_PROMPT.format(
            output_file=output_file,
            objective=objective,
            stage=stage,
        )

    result = await query_agent(
        output_type=SupervisorDecision,
        name="supervisor",
        client=client,
        prompt=prompt,
    )

    if isinstance(result, SupervisorDecision):
        return result.feedback, result.approved

    # Fallback for non-structured response - parse text for approval
    response_text = str(result) if result else ""
    clean = response_text.strip().lstrip("*").strip().upper()
    is_approved = clean.startswith("APPROVED") or "APPROVED:" in clean.upper()
    return response_text, is_approved


async def execute_stage(
    *,
    client: ClaudeSDKClient,
    stage_command: str,
    objective: str,
    supervisor_context: str,
) -> StageResult:
    """Execute a single stage and return the result."""
    from π.schemas import StageOutput

    # Build the stage prompt with objective and any supervisor context
    if supervisor_context:
        prompt = f"/{stage_command} {objective}\n\nContext from tech lead:\n{supervisor_context}"
    else:
        prompt = f"/{stage_command} {objective}"

    result = await query_agent(
        client=client,
        prompt=prompt,
        name="swe",
        output_type=StageOutput,
    )

    if result is None:
        return StageResult(
            stage=stage_command,
            status="error",
            response="No response from agent",
        )

    # Handle structured output
    if isinstance(result, StageOutput):
        return StageResult(
            stage=stage_command,
            status=result.status,
            output_file=result.output_file,
            questions=result.questions,
            response=result.summary,
        )

    # Fallback for non-structured response - assume complete with text response
    return StageResult(
        stage=stage_command,
        status="complete",
        response=str(result),
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
                    questions=result.questions,
                    client=supervisor_client,
                    context=stage_context,
                    stage=stage_command,
                    objective=objective,
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
    from π.schemas import StageOutput, SupervisorDecision

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

    # Create agent options with structured output
    swe_options = get_agent_options(
        system_prompt=SWE_SYSTEM_PROMPT,
        output_schema=StageOutput,
        model="sonnet-4.5",
    )
    supervisor_options = get_agent_options(
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        output_schema=SupervisorDecision,
        model="sonnet-4.5",
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
