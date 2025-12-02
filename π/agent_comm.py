import asyncio
import json
import re
from pathlib import Path
from sys import argv

from claude_agent_sdk import (
    ClaudeSDKClient,
)
from pydantic import BaseModel

from π.agent import get_agent_options
from π.schemas import StageOutput, SupervisorDecision
from π.utils import (
    capture_conversation_to_csv,
    create_workflow_dir,
    extract_message_content,
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


def parse_structured_output(
    output_type: type[BaseModel],
    *,
    structured_output: dict | None = None,
    text_result: str | None = None,
) -> BaseModel | None:
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
        # run the workflow
        success = True

        if success:
            print(f"\n[π-CLI] Workflow completed. Logs at: {workflow_dir}")
        else:
            print(f"\n[π-CLI] Workflow failed. Check logs at: {workflow_dir}")


if __name__ == "__main__":
    objective = " ".join(argv[1:]) if len(argv) > 1 else None
    asyncio.run(main(objective))
