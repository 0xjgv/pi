"""Observer protocol for workflow events.

This module defines the observer protocol and message dispatcher for
visibility into orchestrator tool calls during workflow execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from claude_agent_sdk.types import (
        AssistantMessage,
        Message,
    )


class WorkflowObserver(Protocol):
    """Observer protocol for workflow events.

    Implementations receive events during workflow execution for
    display, logging, metrics collection, etc.
    """

    def on_tool_start(self, name: str, input: dict) -> None:
        """Called when a tool begins execution.

        Args:
            name: The tool name (e.g., "mcp__workflow__research_codebase").
            input: The tool input parameters.
        """
        ...

    def on_tool_end(self, name: str, result: str | None, is_error: bool) -> None:
        """Called when a tool completes execution.

        Args:
            name: The tool name.
            result: The tool result (truncated for display).
            is_error: Whether the tool execution failed.
        """
        ...

    def on_text(self, text: str) -> None:
        """Called when the agent produces text output.

        Args:
            text: The text content from the agent.
        """
        ...

    def on_thinking(self, text: str) -> None:
        """Called when the agent is thinking.

        Args:
            text: The thinking content (if exposed).
        """
        ...

    def on_complete(self, turns: int, cost: float, duration_ms: int) -> None:
        """Called when the workflow completes.

        Args:
            turns: Number of conversation turns.
            cost: Total cost in USD.
            duration_ms: Total duration in milliseconds.
        """
        ...


class LoggingObserver:
    """File-based logging observer for debugging.

    Writes detailed workflow events to a log file for post-mortem analysis.
    Captures tool calls, text output, thinking, and completion metrics.
    """

    def __init__(
        self,
        log_path: Path,
        *,
        objective: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize the logging observer.

        Args:
            log_path: Path to the log file.
            objective: Optional workflow objective to include in header.
            system_prompt: Optional system prompt to include in header.
        """
        self.log_path = log_path
        self.start_time = datetime.now()
        self.objective = objective
        self.system_prompt = system_prompt
        self._write_header()

    def _write_header(self) -> None:
        """Write the log file header."""
        header = [
            "=" * 80,
            f"Workflow Log - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        if self.objective:
            header.append(f"Objective: {self.objective}")
        if self.system_prompt:
            header.append("")
            header.append("System Prompt:")
            header.append("-" * 40)
            header.append(self.system_prompt)
            header.append("-" * 40)
        header.append("=" * 80)
        header.append("")

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(header) + "\n")

    def _log(self, event: str, details: str = "") -> None:
        """Append a log entry.

        Args:
            event: The event type/description.
            details: Optional details to include.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {event}\n"
        if details:
            entry += f"{details}\n"
        entry += "\n"

        with self.log_path.open("a") as f:
            f.write(entry)

    def on_tool_start(self, name: str, input: dict) -> None:
        """Log tool start event."""
        input_json = json.dumps(input, indent=2, default=str)
        self._log(f"TOOL_START: {name}", input_json)

    def on_tool_end(self, name: str, result: str | None, is_error: bool) -> None:
        """Log tool end event."""
        status = "ERROR" if is_error else "OK"
        details = f"Result: {result}" if result else ""
        self._log(f"TOOL_END: {name} [{status}]", details)

    def on_text(self, text: str) -> None:
        """Log text output event."""
        self._log("TEXT:", text)

    def on_thinking(self, text: str) -> None:
        """Log thinking event."""
        self._log("THINKING:", text)

    def on_complete(self, turns: int, cost: float, duration_ms: int) -> None:
        """Log completion event with summary."""
        duration_s = duration_ms / 1000
        summary = f"Turns: {turns} | Cost: ${cost:.4f} | Duration: {duration_s:.1f}s"
        self._log("COMPLETE", summary)

        # Write footer
        with self.log_path.open("a") as f:
            f.write("=" * 80 + "\n")


class CompositeObserver:
    """Dispatches events to multiple observers.

    Allows combining multiple observer implementations (e.g., LiveObserver
    for display and LoggingObserver for file logging).
    """

    def __init__(self, observers: list[WorkflowObserver]) -> None:
        """Initialize with a list of observers.

        Args:
            observers: List of observers to dispatch events to.
        """
        self.observers = observers

    def on_tool_start(self, name: str, input: dict) -> None:
        """Dispatch tool start to all observers."""
        for obs in self.observers:
            obs.on_tool_start(name, input)

    def on_tool_end(self, name: str, result: str | None, is_error: bool) -> None:
        """Dispatch tool end to all observers."""
        for obs in self.observers:
            obs.on_tool_end(name, result, is_error)

    def on_text(self, text: str) -> None:
        """Dispatch text to all observers."""
        for obs in self.observers:
            obs.on_text(text)

    def on_thinking(self, text: str) -> None:
        """Dispatch thinking to all observers."""
        for obs in self.observers:
            obs.on_thinking(text)

    def on_complete(self, turns: int, cost: float, duration_ms: int) -> None:
        """Dispatch completion to all observers."""
        for obs in self.observers:
            obs.on_complete(turns, cost, duration_ms)


def dispatch_message(message: Message, observer: WorkflowObserver) -> None:
    """Dispatch SDK message to appropriate observer method.

    Args:
        message: The SDK message to dispatch.
        observer: The observer to receive events.
    """
    # Import here to avoid circular imports and for isinstance checks
    from claude_agent_sdk.types import (  # noqa: PLC0415
        AssistantMessage,
        ResultMessage,
    )

    if isinstance(message, AssistantMessage):
        _dispatch_assistant_message(message, observer)
    elif isinstance(message, ResultMessage):
        observer.on_complete(
            turns=message.num_turns,
            cost=message.total_cost_usd or 0.0,
            duration_ms=message.duration_ms,
        )


def _dispatch_assistant_message(
    message: AssistantMessage,
    observer: WorkflowObserver,
) -> None:
    """Dispatch content blocks from an assistant message.

    Args:
        message: The assistant message containing content blocks.
        observer: The observer to receive events.
    """
    from claude_agent_sdk.types import (  # noqa: PLC0415
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
    )

    for block in message.content:
        if isinstance(block, ToolUseBlock):
            observer.on_tool_start(name=block.name, input=block.input)
        elif isinstance(block, ToolResultBlock):
            # Extract result text (may be string or list)
            result_text = None
            if isinstance(block.content, str):
                result_text = block.content[:200] if block.content else None
            elif isinstance(block.content, list) and block.content:
                # Take first text item if list
                first = block.content[0]
                if isinstance(first, dict) and "text" in first:
                    result_text = first["text"][:200]
            observer.on_tool_end(
                name=block.tool_use_id,
                result=result_text,
                is_error=block.is_error or False,
            )
        elif isinstance(block, TextBlock):
            observer.on_text(text=block.text)
        elif isinstance(block, ThinkingBlock):
            observer.on_thinking(text=block.thinking)
