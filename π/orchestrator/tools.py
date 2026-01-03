"""Tool functions for orchestrator agent."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from π.orchestrator.state import (
    DEFAULT_MAX_VALIDATION_RETRIES,
    Task,
    TaskStatus,
    TaskStrategy,
    WorkflowState,
    save_state,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of implementation validation.

    Attributes:
        passed: Whether all validation checks passed.
        failures: List of failure messages.
    """

    passed: bool
    failures: list[str]


@dataclass
class WorkflowResult:
    """Result of workflow execution.

    Attributes:
        success: Whether the workflow completed successfully.
        outputs: Artifacts produced by the workflow.
        error: Error message if workflow failed.
    """

    success: bool
    outputs: dict[str, str]
    error: str | None = None


def get_next_task(state: WorkflowState) -> Task | None:
    """Get next pending task using depth-first traversal.

    Priority: incomplete subtasks before siblings.

    Args:
        state: Current workflow state.

    Returns:
        Next pending task or None if no tasks pending.
    """
    for task in state.tasks:
        if task.status == TaskStatus.PENDING:
            # Check if this task has incomplete subtasks
            subtasks = [t for t in state.tasks if t.parent_id == task.id]
            incomplete_subtasks = [
                t for t in subtasks if t.status != TaskStatus.COMPLETED
            ]
            if incomplete_subtasks:
                # Return first incomplete subtask
                for subtask in incomplete_subtasks:
                    if subtask.status == TaskStatus.PENDING:
                        return subtask
            return task
    return None


def add_task(
    state: WorkflowState,
    description: str,
    *,
    parent_id: str | None = None,
    root: Path | None = None,
) -> str:
    """Add new task to state, return task_id.

    Args:
        state: Current workflow state.
        description: Task description.
        parent_id: Optional parent task ID for subtask hierarchy.
        root: Root path for state persistence.

    Returns:
        New task ID.
    """
    task_id = f"t{len(state.tasks) + 1}"
    task = Task(
        id=task_id,
        description=description,
        status=TaskStatus.PENDING,
        parent_id=parent_id,
    )
    state.tasks.append(task)
    save_state(state, root)
    logger.info("Added task %s: %s", task_id, description[:50])
    return task_id


def mark_in_progress(
    state: WorkflowState,
    task_id: str,
    *,
    root: Path | None = None,
) -> None:
    """Mark task as in progress.

    Args:
        state: Current workflow state.
        task_id: ID of task to mark.
        root: Root path for state persistence.

    Raises:
        ValueError: If task not found.
    """
    for task in state.tasks:
        if task.id == task_id:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now().isoformat()
            save_state(state, root)
            logger.info("Task %s marked in progress", task_id)
            return
    raise ValueError(f"Task {task_id} not found")


def mark_complete(
    state: WorkflowState,
    task_id: str,
    *,
    outputs: dict[str, str] | None = None,
    root: Path | None = None,
) -> None:
    """Mark task as completed with optional outputs.

    Args:
        state: Current workflow state.
        task_id: ID of task to mark.
        outputs: Artifacts produced by this task.
        root: Root path for state persistence.

    Raises:
        ValueError: If task not found.
    """
    for task in state.tasks:
        if task.id == task_id:
            task.status = TaskStatus.COMPLETED
            task.outputs = outputs or {}
            task.completed_at = datetime.now().isoformat()
            save_state(state, root)
            logger.info("Task %s marked complete", task_id)
            return
    raise ValueError(f"Task {task_id} not found")


def mark_blocked(
    state: WorkflowState,
    task_id: str,
    *,
    reason: str,
    root: Path | None = None,
) -> None:
    """Mark task as blocked with reason.

    Args:
        state: Current workflow state.
        task_id: ID of task to mark.
        reason: Reason for blocking.
        root: Root path for state persistence.

    Raises:
        ValueError: If task not found.
    """
    for task in state.tasks:
        if task.id == task_id:
            task.status = TaskStatus.BLOCKED
            task.last_validation_failure = reason
            save_state(state, root)
            logger.warning("Task %s blocked: %s", task_id, reason[:100])
            return
    raise ValueError(f"Task {task_id} not found")


def increment_validation_retry(
    state: WorkflowState,
    task_id: str,
    *,
    failure_message: str,
    root: Path | None = None,
) -> int:
    """Increment validation retry counter for task.

    Args:
        state: Current workflow state.
        task_id: ID of task.
        failure_message: Validation failure message.
        root: Root path for state persistence.

    Returns:
        New retry count.

    Raises:
        ValueError: If task not found.
    """
    for task in state.tasks:
        if task.id == task_id:
            task.validation_retries += 1
            task.last_validation_failure = failure_message
            save_state(state, root)
            logger.info(
                "Task %s validation retry %d: %s",
                task_id,
                task.validation_retries,
                failure_message[:100],
            )
            return task.validation_retries
    raise ValueError(f"Task {task_id} not found")


def validate_implementation(
    task: Task,
    *,
    project_root: Path | None = None,
) -> ValidationResult:
    """Run validation checks on implementation.

    Executes:
    1. make check (lint/type checking)
    2. make test (test suite)

    Args:
        task: Task that was implemented.
        project_root: Root path for running commands.

    Returns:
        ValidationResult with passed status and any failures.
    """
    failures: list[str] = []
    cwd = project_root or Path.cwd()

    # 1. Type/lint checking
    logger.info("Running validation: make check")
    try:
        result = subprocess.run(
            ["make", "check"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            error_preview = result.stderr[:500] if result.stderr else result.stdout[:500]
            failures.append(f"Type/lint check failed: {error_preview}")
            logger.warning("make check failed: %s", error_preview[:200])
    except subprocess.TimeoutExpired:
        failures.append("Type/lint check timed out after 5 minutes")
        logger.error("make check timed out")
    except FileNotFoundError:
        logger.debug("make not found, skipping check")

    # 2. Test suite
    logger.info("Running validation: make test")
    try:
        result = subprocess.run(
            ["make", "test"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        if result.returncode != 0:
            error_preview = result.stderr[:500] if result.stderr else result.stdout[:500]
            failures.append(f"Tests failed: {error_preview}")
            logger.warning("make test failed: %s", error_preview[:200])
    except subprocess.TimeoutExpired:
        failures.append("Tests timed out after 10 minutes")
        logger.error("make test timed out")
    except FileNotFoundError:
        logger.debug("make not found, skipping test")

    return ValidationResult(
        passed=len(failures) == 0,
        failures=failures,
    )


def should_retry_validation(task: Task) -> bool:
    """Check if task can retry validation.

    Args:
        task: Task to check.

    Returns:
        True if retries remaining, False otherwise.
    """
    return task.validation_retries < DEFAULT_MAX_VALIDATION_RETRIES


def get_state_summary(state: WorkflowState) -> str:
    """Generate human-readable state summary.

    Args:
        state: Current workflow state.

    Returns:
        Summary string for DSPy input.
    """
    completed = [t for t in state.tasks if t.status == TaskStatus.COMPLETED]
    pending = [t for t in state.tasks if t.status == TaskStatus.PENDING]
    in_progress = [t for t in state.tasks if t.status == TaskStatus.IN_PROGRESS]
    blocked = [t for t in state.tasks if t.status == TaskStatus.BLOCKED]

    lines = [
        f"Objective: {state.objective}",
        f"Iteration: {state.config.current_iteration}/{state.config.max_iterations}",
        f"Status: {state.status.value}",
        "",
        f"Completed ({len(completed)}):",
    ]

    for t in completed:
        lines.append(f"  - [{t.id}] {t.description[:60]}")

    lines.append(f"\nIn Progress ({len(in_progress)}):")
    for t in in_progress:
        lines.append(f"  - [{t.id}] {t.description[:60]}")

    lines.append(f"\nPending ({len(pending)}):")
    for t in pending:
        lines.append(f"  - [{t.id}] {t.description[:60]}")

    if blocked:
        lines.append(f"\nBlocked ({len(blocked)}):")
        for t in blocked:
            lines.append(f"  - [{t.id}] {t.description[:60]}: {t.last_validation_failure or 'Unknown'}")

    return "\n".join(lines)


def format_status_display(state: WorkflowState) -> str:
    """Format state for CLI status display.

    Args:
        state: Current workflow state.

    Returns:
        Formatted string for terminal output.
    """
    status_icons = {
        TaskStatus.PENDING: "[dim][ ][/dim]",
        TaskStatus.IN_PROGRESS: "[yellow][~][/yellow]",
        TaskStatus.COMPLETED: "[green][x][/green]",
        TaskStatus.BLOCKED: "[red][!][/red]",
    }

    strategy_badges = {
        TaskStrategy.FULL_WORKFLOW: "[blue]full[/blue]",
        TaskStrategy.QUICK_CHANGE: "[cyan]quick[/cyan]",
    }

    lines = [
        f"[bold]Objective:[/bold] {state.objective}",
        f"[bold]Hash:[/bold] {state.objective_hash}",
        f"[bold]Status:[/bold] {state.status.value}",
        f"[bold]Iteration:[/bold] {state.config.current_iteration}/{state.config.max_iterations}",
        "",
        "[bold]Tasks:[/bold]",
    ]

    # Build task tree
    root_tasks = [t for t in state.tasks if t.parent_id is None]

    def render_task(task: Task, indent: int = 0) -> list[str]:
        prefix = "  " * indent
        icon = status_icons.get(task.status, "[ ]")
        badge = strategy_badges.get(task.strategy, "") if task.strategy else ""
        badge_str = f" {badge}" if badge else ""

        task_lines = [f"{prefix}{icon} [{task.id}] {task.description}{badge_str}"]

        # Add validation retry info if applicable
        if task.validation_retries > 0:
            task_lines.append(
                f"{prefix}    [dim]Retries: {task.validation_retries}/{DEFAULT_MAX_VALIDATION_RETRIES}[/dim]"
            )

        # Render subtasks
        subtasks = [t for t in state.tasks if t.parent_id == task.id]
        for subtask in subtasks:
            task_lines.extend(render_task(subtask, indent + 1))

        return task_lines

    for task in root_tasks:
        lines.extend(render_task(task))

    if state.halt_reason:
        lines.append("")
        lines.append(f"[red]Halted:[/red] {state.halt_reason}")

    return "\n".join(lines)
