"""Queue-based stage communication for Claude SDK."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage
from pydantic import BaseModel

from π.config import get_agent_options

from .logging import log_queue_receive, log_queue_send
from .models import (
    CommitOutput,
    CreatePlanOutput,
    ImplementOutput,
    IteratePlanOutput,
    ResearchOutput,
    ReviewPlanOutput,
)

logger = logging.getLogger(__name__)

# Known ResultMessage subtypes (not enforced by SDK types, handle gracefully)
_SUCCESS_SUBTYPES = {"success"}
_ERROR_SUBTYPES = {"error_max_structured_output_retries", "error"}

# Pre-configured tool lists for each stage (matches current workflow/bridge.py)
RESEARCH_TOOLS = ["Read", "Glob", "Grep", "Skill"]  # Read-only + research skill
DESIGN_TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Skill"]
EXECUTE_TOOLS = ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Skill"]


@dataclass
class StageQueue[T: BaseModel]:
    """Message queue for a workflow stage.

    Maintains a persistent SDK session via ClaudeSDKClient and enforces typed outputs.

    Note: Uses ClaudeSDKClient (not standalone query()) because session continuation
    requires the client's query(prompt, session_id=...) pattern.
    """

    name: str
    output_schema: type[T]
    allowed_tools: list[str]
    session_id: str | None = field(default=None)
    message_history: list[dict[str, Any]] = field(default_factory=list)

    def _get_options(self) -> dict[str, Any]:
        """Build options dict with output schema for get_agent_options override."""
        base_options = get_agent_options()
        # Override with stage-specific settings
        return {
            "allowed_tools": self.allowed_tools,
            "output_format": {
                "type": "json_schema",
                "schema": self.output_schema.model_json_schema(),
            },
            "hooks": base_options.hooks,
            "permission_mode": base_options.permission_mode,
            "setting_sources": base_options.setting_sources,
            "can_use_tool": base_options.can_use_tool,
            "cwd": base_options.cwd,
        }

    async def send(self, message: str) -> T:
        """Send a message to this stage and await typed response.

        Uses ClaudeSDKClient for proper session management. The session_id
        is passed to client.query() for continuation.

        Args:
            message: The prompt/instruction to send

        Returns:
            Validated output matching output_schema

        Raises:
            ValueError: If structured output validation fails or no result received
        """
        self.message_history.append({"role": "user", "content": message})
        start_time = time.perf_counter()

        log_queue_send(self.name, message)

        options = ClaudeAgentOptions(**self._get_options())
        async with ClaudeSDKClient(options=options) as client:
            await client.query(message, session_id=self.session_id or "default")

            async for msg in client.receive_response():
                if isinstance(msg, ResultMessage):
                    # Store session_id for continuation
                    self.session_id = msg.session_id
                    duration_ms = (time.perf_counter() - start_time) * 1000

                    # Handle structured output (success case)
                    if msg.structured_output is not None:
                        output = self.output_schema.model_validate(
                            msg.structured_output
                        )
                        self.message_history.append({
                            "role": "assistant",
                            "content": output.model_dump_json(),
                            "duration_ms": duration_ms,
                        })
                        log_queue_receive(self.name, output, duration_ms)
                        return output

                    # Handle known error subtypes
                    if msg.subtype in _ERROR_SUBTYPES:
                        raise ValueError(
                            f"Stage {self.name}: {msg.subtype} - "
                            f"{msg.result or 'no details'}"
                        )

                    # Handle unknown subtypes gracefully
                    if msg.subtype not in _SUCCESS_SUBTYPES:
                        raise ValueError(
                            f"Stage {self.name}: Unknown subtype '{msg.subtype}'"
                        )

        raise ValueError(f"Stage {self.name}: No result message received")

    def clear_session(self) -> None:
        """Clear session state for fresh start."""
        self.session_id = None
        self.message_history.clear()


def create_research_queue() -> StageQueue[ResearchOutput]:
    """Create queue for research stage."""
    return StageQueue(
        name="research",
        output_schema=ResearchOutput,
        allowed_tools=RESEARCH_TOOLS,
    )


def create_design_queue(
    sub_stage: Literal["create", "review", "iterate"],
) -> (
    StageQueue[CreatePlanOutput]
    | StageQueue[ReviewPlanOutput]
    | StageQueue[IteratePlanOutput]
):
    """Create queue for design sub-stage."""
    schemas: dict[str, type[BaseModel]] = {
        "create": CreatePlanOutput,
        "review": ReviewPlanOutput,
        "iterate": IteratePlanOutput,
    }
    return StageQueue(
        name=f"design_{sub_stage}",
        output_schema=schemas[sub_stage],
        allowed_tools=DESIGN_TOOLS,
    )


def create_execute_queue(
    sub_stage: Literal["implement", "commit"],
) -> StageQueue[ImplementOutput] | StageQueue[CommitOutput]:
    """Create queue for execute sub-stage."""
    schemas: dict[str, type[BaseModel]] = {
        "implement": ImplementOutput,
        "commit": CommitOutput,
    }
    return StageQueue(
        name=f"execute_{sub_stage}",
        output_schema=schemas[sub_stage],
        allowed_tools=EXECUTE_TOOLS,
    )
