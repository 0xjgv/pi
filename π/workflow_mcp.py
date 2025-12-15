"""MCP server for workflow state control."""

from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeSDKClient, create_sdk_mcp_server, tool


# Workflow state stored in-memory
class WorkflowState:
    """In-memory workflow state manager."""

    def __init__(self, objective: str):
        self.objective = objective
        self.current_stage_index = 0
        self.context = objective
        self.completed_stages: list[str] = []
        self.stage_outputs: dict[str, str] = {}  # stage -> output_file

    @property
    def current_stage(self) -> str | None:
        stages = ["research", "plan", "implement"]
        if self.current_stage_index < len(stages):
            return stages[self.current_stage_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.current_stage_index >= 3

    def advance(self, output_file: str | None = None) -> str | None:
        """Advance to next stage, return next stage name."""
        if self.current_stage:
            self.completed_stages.append(self.current_stage)
            if output_file:
                self.stage_outputs[self.current_stage] = output_file
                self.context = output_file
        self.current_stage_index += 1
        return self.current_stage

    def reset(self) -> None:
        """Reset workflow state to initial values, preserving objective."""
        self.current_stage_index = 0
        self.context = self.objective
        self.completed_stages = []
        self.stage_outputs = {}


# Global state - set by workflow orchestrator before agent runs
_workflow_state: WorkflowState | None = None
_supervisor_client: ClaudeSDKClient | None = None


def set_workflow_context(state: WorkflowState, supervisor: ClaudeSDKClient) -> None:
    """Set workflow context for MCP tools. Called by orchestrator."""
    global _workflow_state, _supervisor_client
    _workflow_state = state
    _supervisor_client = supervisor


def get_workflow_state() -> WorkflowState:
    """Get current workflow state."""
    if _workflow_state is None:
        raise RuntimeError("Workflow state not initialized")
    return _workflow_state


# Stage output patterns for validation
STAGE_OUTPUT_PATTERNS = {
    "research": "thoughts/shared/research/",
    "plan": "thoughts/shared/plans/",
    "implement": None,  # No file required
}


@tool(
    name="complete_stage",
    description="Signal that the current workflow stage is complete. Call this when you have finished the stage work and created any required output files.",
    input_schema={
        "stage": str,  # "research" | "plan" | "implement"
        "summary": str,  # What was accomplished
        "output_file": str,  # Path to output artifact (optional for implement)
    },
)
async def complete_stage(args: dict[str, Any]) -> dict[str, Any]:
    """Signal stage completion and advance workflow state."""
    state = get_workflow_state()

    stage = args["stage"]
    summary = args["summary"]
    output_file = args.get("output_file")

    # Validate stage matches current
    if stage != state.current_stage:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Cannot complete '{stage}'. Current stage is '{state.current_stage}'.",
                }
            ],
            "is_error": True,
        }

    # Validate output file exists (for research and plan stages)
    expected_pattern = STAGE_OUTPUT_PATTERNS.get(stage)
    if expected_pattern and output_file:
        if not Path(output_file).exists():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Output file not found: {output_file}",
                    }
                ],
                "is_error": True,
            }
        if expected_pattern not in output_file:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Output file must be in {expected_pattern}, got: {output_file}",
                    }
                ],
                "is_error": True,
            }
    elif expected_pattern and not output_file:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Stage '{stage}' requires an output_file in {expected_pattern}",
                }
            ],
            "is_error": True,
        }

    # Advance state
    next_stage = state.advance(output_file)

    result = {
        "stage_completed": stage,
        "summary": summary,
        "output_file": output_file,
        "next_stage": next_stage,
        "workflow_complete": state.is_complete,
    }

    return {"content": [{"type": "text", "text": str(result)}]}


@tool(
    name="ask_supervisor",
    description="Ask the tech lead a question when you need clarification or guidance. Use this when blocked or uncertain about how to proceed.",
    input_schema={
        "question": str,  # The question to ask
        "context": str,  # Relevant context for the question
    },
)
async def ask_supervisor(args: dict[str, Any]) -> dict[str, Any]:
    """Query supervisor and return answer inline."""
    global _supervisor_client

    if _supervisor_client is None:
        return {
            "content": [{"type": "text", "text": "Error: Supervisor not available"}],
            "is_error": True,
        }

    state = get_workflow_state()
    question = args["question"]
    context = args.get("context", "")

    prompt = f"""You are the tech lead supervising an automated workflow.

**Workflow Objective**: {state.objective}

**Current Stage**: {state.current_stage}

**Context**: {context}

**Question from the software engineer**:
{question}

Provide a clear, actionable answer. Be decisive - make a recommendation if uncertain.
Do NOT ask follow-up questions. Make decisions and move forward."""

    await _supervisor_client.query(prompt=prompt)

    messages: list[str] = []
    async for msg in _supervisor_client.receive_response():
        if hasattr(msg, "content"):
            content = msg.content
            if isinstance(content, str):
                messages.append(content)
            elif isinstance(content, list):
                for block in content:
                    if hasattr(block, "text"):
                        messages.append(block.text)

    answer = messages[-1] if messages else "No response from supervisor"

    return {"content": [{"type": "text", "text": f"Supervisor's answer:\n\n{answer}"}]}


@tool(
    name="get_current_stage",
    description="Get information about the current workflow stage, including requirements and context.",
    input_schema={},  # No parameters
)
async def get_current_stage(args: dict[str, Any]) -> dict[str, Any]:
    """Return current workflow state information."""
    state = get_workflow_state()

    stage_commands = {
        "research": "/1_research_codebase",
        "plan": "/2_create_plan",
        "implement": "/3_implement_plan",
    }

    stage_requirements = {
        "research": "Create a research document in thoughts/shared/research/",
        "plan": "Create an implementation plan in thoughts/shared/plans/",
        "implement": "Implement the plan. No output file required.",
    }

    info = {
        "current_stage": state.current_stage,
        "stage_index": state.current_stage_index + 1,
        "total_stages": 3,
        "context": state.context,
        "command": stage_commands.get(state.current_stage),
        "requirements": stage_requirements.get(state.current_stage),
        "completed_stages": state.completed_stages,
        "workflow_complete": state.is_complete,
    }

    return {"content": [{"type": "text", "text": str(info)}]}


def create_workflow_server(mcp_name: str = "workflow"):
    """Create the workflow MCP server."""
    return create_sdk_mcp_server(
        tools=[complete_stage, ask_supervisor, get_current_stage],
        version="1.0.0",
        name=mcp_name,
    )
