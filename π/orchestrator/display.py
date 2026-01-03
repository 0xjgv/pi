"""Rich-based progress display for orchestrator execution.

Provides a live-updating terminal display showing:
- Current task and its execution stage
- Next tasks in queue (max 3)
- Overall progress (tasks completed, iterations)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Generator

    from π.orchestrator.state import Task, TaskStage, WorkflowState

logger = logging.getLogger(__name__)

# Stage order for progress bar calculation
STAGE_ORDER: list[str] = [
    "pending",
    "assessing complexity",
    "researching codebase",
    "creating plan",
    "reviewing plan",
    "iterating on plan",
    "implementing changes",
    "creating commit",
    "validating changes",
    "complete",
]


def _get_stage_progress(stage: str) -> tuple[int, int]:
    """Get current stage index and total stages.

    Args:
        stage: Current stage value.

    Returns:
        Tuple of (current_index, total_stages).
    """
    try:
        idx = STAGE_ORDER.index(stage)
    except ValueError:
        idx = 0
    return idx, len(STAGE_ORDER) - 1  # -1 because 'complete' is the end


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


class OrchestratorDisplay:
    """Live progress display for orchestrator execution.

    Displays a rich panel with:
    - Current task and stage progress
    - Next 3 pending tasks
    - Overall completion stats
    """

    def __init__(self, *, console: Console | None = None):
        """Initialize display.

        Args:
            console: Rich console instance. Creates new one if not provided.
        """
        self.console = console or Console()
        self._live: Live | None = None
        self._current_task: Task | None = None
        self._state: WorkflowState | None = None

        # Stage progress bar
        self._stage_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=20),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=True,
        )
        self._stage_task_id: int | None = None

    def _build_display(self) -> Panel:
        """Build the display panel content."""
        if self._state is None:
            return Panel("No state", title="π Orchestrator")

        # Build content group
        content_parts = []

        # Current task section
        current_section = self._build_current_task_section()
        content_parts.append(current_section)

        # Next tasks section
        next_section = self._build_next_tasks_section()
        if next_section:
            content_parts.append(Text())  # Spacer
            content_parts.append(next_section)

        # Progress section
        progress_section = self._build_progress_section()
        content_parts.append(Text())  # Spacer
        content_parts.append(progress_section)

        return Panel(
            Group(*content_parts),
            title="[bold cyan]π Orchestrator[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )

    def _build_current_task_section(self) -> Table:
        """Build current task display section."""
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()

        if self._current_task:
            task = self._current_task
            desc = _truncate(task.description, 55)
            stage_val = task.stage.value if hasattr(task.stage, "value") else str(task.stage)

            table.add_row("▸ Current:", f"[white]{desc}[/white]")

            # Stage with progress
            current_idx, total = _get_stage_progress(stage_val)
            stage_display = f"[yellow]{stage_val}[/yellow] ({current_idx}/{total})"
            table.add_row("  └─ Stage:", stage_display)

            # Strategy if set
            if task.strategy:
                strategy_val = task.strategy.value if hasattr(task.strategy, "value") else str(task.strategy)
                color = "blue" if strategy_val == "full_workflow" else "cyan"
                table.add_row("  └─ Strategy:", f"[{color}]{strategy_val}[/{color}]")
        else:
            table.add_row("▸ Current:", "[dim]No active task[/dim]")

        return table

    def _build_next_tasks_section(self) -> Table | None:
        """Build next tasks display section."""
        if not self._state:
            return None

        # Get pending tasks (excluding current)
        current_id = self._current_task.id if self._current_task else None
        pending = [
            t for t in self._state.tasks
            if t.status.value == "pending" and t.id != current_id
        ][:3]  # Max 3

        if not pending:
            return None

        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()

        table.add_row("▸ Up Next:", "")
        for i, task in enumerate(pending, 1):
            desc = _truncate(task.description, 50)
            table.add_row(f"  {i}.", f"[dim]{desc}[/dim]")

        return table

    def _build_progress_section(self) -> Text:
        """Build overall progress section."""
        if not self._state:
            return Text("No state")

        completed = sum(1 for t in self._state.tasks if t.status.value == "completed")
        total = len(self._state.tasks)
        iteration = self._state.config.current_iteration
        max_iter = self._state.config.max_iterations

        text = Text()
        text.append("▸ Progress: ", style="bold")
        text.append(f"{completed}/{total} tasks", style="green" if completed == total else "white")
        text.append(" · ")
        text.append(f"Iteration {iteration}/{max_iter}", style="cyan")

        return text

    @contextmanager
    def live_display(self, state: WorkflowState) -> Generator[None, None, None]:
        """Context manager for live display updates.

        Args:
            state: Initial workflow state.

        Yields:
            None - use update methods to refresh display.
        """
        self._state = state
        self._live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )

        try:
            with self._live:
                logger.debug("Started live display")
                yield
        finally:
            self._live = None
            self._current_task = None
            logger.debug("Stopped live display")

    def update_state(self, state: WorkflowState) -> None:
        """Update display with new state.

        Args:
            state: Updated workflow state.
        """
        self._state = state
        self._refresh()

    def update_current_task(self, task: Task | None) -> None:
        """Update current task being executed.

        Args:
            task: Current task or None if idle.
        """
        self._current_task = task
        self._refresh()

    def update_stage(self, stage: TaskStage) -> None:
        """Update current task's stage.

        Args:
            stage: New execution stage.
        """
        if self._current_task:
            self._current_task.stage = stage
            self._refresh()
            logger.info("Stage: %s", stage.value)

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self._live:
            self._live.update(self._build_display())

    def log_iteration(self, iteration: int, max_iterations: int) -> None:
        """Log iteration start.

        Args:
            iteration: Current iteration number (1-indexed for display).
            max_iterations: Maximum iterations allowed.
        """
        logger.info("=== Iteration %d/%d ===", iteration, max_iterations)

    def log_task_start(self, task: Task) -> None:
        """Log task start.

        Args:
            task: Task being started.
        """
        logger.info("Starting task [%s]: %s", task.id, task.description[:80])

    def log_task_complete(self, task: Task) -> None:
        """Log task completion.

        Args:
            task: Completed task.
        """
        logger.info("Completed task [%s]: %s", task.id, task.description[:50])

    def log_workflow_result(
        self,
        *,
        strategy: str,
        success: bool,
        outputs: dict[str, str] | None = None,
    ) -> None:
        """Log workflow execution result.

        Args:
            strategy: Workflow strategy used (quick/full).
            success: Whether workflow succeeded.
            outputs: Optional output artifacts.
        """
        status = "SUCCESS" if success else "FAILED"
        logger.info("Workflow [%s] %s", strategy, status)
        if outputs:
            for key, value in outputs.items():
                logger.debug("  %s: %s", key, str(value)[:100])


# Convenience function for simple usage
def create_display(console: Console | None = None) -> OrchestratorDisplay:
    """Create a new orchestrator display.

    Args:
        console: Optional rich console to use.

    Returns:
        New OrchestratorDisplay instance.
    """
    return OrchestratorDisplay(console=console)
