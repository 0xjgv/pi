"""Rich Live display observer for workflow visibility.

This module implements the WorkflowObserver protocol using Rich's Live
display for real-time progress tracking during workflow execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from types import TracebackType


@dataclass
class ToolState:
    """State for a single tool execution."""

    name: str
    input_keys: list[str]
    status: str = "running"  # running, done, error
    result_preview: str | None = None


class LiveObserver:
    """Rich Live display observer for workflow events.

    Provides real-time visual feedback during workflow execution,
    showing active tools, completed steps, and final summary.

    Usage:
        observer = LiveObserver()
        with observer:
            async for message in client.receive_response():
                dispatch_message(message, observer)
    """

    def __init__(self) -> None:
        """Initialize the live observer."""
        self.console = Console()
        self.live: Live | None = None
        self.current_tool: ToolState | None = None
        self.completed_tools: list[ToolState] = []
        self.last_text: str = ""

    def __enter__(self) -> LiveObserver:
        """Start the live display context."""
        self.live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        )
        self.live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the live display context."""
        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)
            self.live = None

    def on_tool_start(self, name: str, input: dict) -> None:
        """Handle tool start event."""
        # Finish previous tool if any (in case on_tool_end wasn't called)
        if self.current_tool:
            self.current_tool.status = "done"
            self.completed_tools.append(self.current_tool)

        self.current_tool = ToolState(
            name=_format_tool_name(name),
            input_keys=list(input.keys()),
        )
        self._refresh()

    def on_tool_end(self, name: str, result: str | None, is_error: bool) -> None:
        """Handle tool end event."""
        if self.current_tool:
            self.current_tool.status = "error" if is_error else "done"
            self.current_tool.result_preview = result[:100] if result else None
            self.completed_tools.append(self.current_tool)
            self.current_tool = None
            self._refresh()

    def on_text(self, text: str) -> None:
        """Handle text output event."""
        self.last_text = text[:200] if text else ""
        self._refresh()

    def on_thinking(self, text: str) -> None:
        """Handle thinking event."""
        # Could show a thinking indicator, for now just track

    def on_complete(self, turns: int, cost: float, duration_ms: int) -> None:
        """Handle workflow completion event."""
        # Finish current tool if any
        if self.current_tool:
            self.current_tool.status = "done"
            self.completed_tools.append(self.current_tool)
            self.current_tool = None

        # Stop live display and print summary
        if self.live:
            self.live.stop()

        self._print_summary(turns, cost, duration_ms)

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self.live:
            self.live.update(self._render())

    def _render(self) -> Panel:
        """Render the current state as a Rich Panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Status", width=3)
        table.add_column("Tool", style="bold")
        table.add_column("Details", style="dim")

        # Completed tools
        for tool in self.completed_tools[-5:]:  # Show last 5
            status = "✓" if tool.status == "done" else "✗"
            style = "green" if tool.status == "done" else "red"
            table.add_row(
                Text(status, style=style),
                tool.name,
                ", ".join(tool.input_keys) if tool.input_keys else "",
            )

        # Current tool
        if self.current_tool:
            table.add_row(
                Text("◐", style="yellow"),
                Text(self.current_tool.name, style="yellow bold"),
                ", ".join(self.current_tool.input_keys),
            )

        return Panel(
            table,
            title="[bold blue]Workflow Progress[/bold blue]",
            border_style="blue",
        )

    def _print_summary(self, turns: int, cost: float, duration_ms: int) -> None:
        """Print the final summary after completion."""
        duration_s = duration_ms / 1000

        summary = Table(show_header=False, box=None)
        summary.add_column("Label", style="bold")
        summary.add_column("Value")

        summary.add_row("Tools", str(len(self.completed_tools)))
        summary.add_row("Turns", str(turns))
        summary.add_row("Cost", f"${cost:.4f}")
        summary.add_row("Duration", f"{duration_s:.1f}s")

        self.console.print()
        self.console.print(
            Panel(
                summary,
                title="[bold green]✓ Workflow Complete[/bold green]",
                border_style="green",
            )
        )


def _format_tool_name(name: str) -> str:
    """Format tool name for display.

    Strips MCP prefix and converts to readable format.
    e.g., "mcp__workflow__research_codebase" -> "research_codebase"
    """
    if name.startswith("mcp__workflow__"):
        return name[15:]  # len("mcp__workflow__")
    if name.startswith("mcp__"):
        return name[5:]
    return name
