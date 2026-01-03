"""State Machine for Long-Running Tasks.

Provides a persistent state machine that tracks progress through complex,
multi-phase objectives. Designed for tasks that may span multiple sessions
and require careful tracking of what's been done and what remains.

Example usage:
    >>> machine = TaskStateMachine.load_or_create("scam-phone-app")
    >>> machine.set_objective("Build app for storing scamming phone numbers with sync")
    >>> machine.decompose_goal(subtasks=[...])
    >>> while not machine.is_complete:
    ...     task = machine.current_task
    ...     result = execute_task(task)
    ...     machine.complete_current_task(result)
    ...     machine.checkpoint()
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from π.support.directory import get_project_root

logger = logging.getLogger(__name__)

# Default state directory
STATE_DIR = Path(".π/state")


class TaskStatus(StrEnum):
    """Status of an individual task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class MachineState(StrEnum):
    """Overall state of the state machine."""

    UNINITIALIZED = "uninitialized"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(StrEnum):
    """Priority levels for tasks."""

    CRITICAL = "critical"  # Must complete, blocks everything
    HIGH = "high"  # Important, should do soon
    NORMAL = "normal"  # Standard priority
    LOW = "low"  # Nice to have
    DEFERRED = "deferred"  # Do later


@dataclass
class TaskResult:
    """Result of a completed task."""

    success: bool
    output: str
    artifacts: list[str] = field(default_factory=list)  # Files created, paths, etc.
    error: str | None = None
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """A single task within the state machine."""

    id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    dependencies: list[str] = field(default_factory=list)  # Task IDs this depends on
    parent_id: str | None = None  # For subtask hierarchy
    result: TaskResult | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    started_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    tags: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)  # Task-specific context

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for serialization."""
        data = asdict(self)
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        if self.result:
            data["result"] = asdict(self.result)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create task from dictionary."""
        data = data.copy()
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        if data.get("result"):
            data["result"] = TaskResult(**data["result"])
        return cls(**data)

    @property
    def is_actionable(self) -> bool:
        """Check if task can be worked on (pending and deps satisfied)."""
        return self.status == TaskStatus.PENDING

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
        )


@dataclass
class Checkpoint:
    """A saved checkpoint of machine state."""

    id: str
    timestamp: str
    state: MachineState
    current_task_id: str | None
    completed_task_ids: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert checkpoint to dictionary."""
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create checkpoint from dictionary."""
        data = data.copy()
        data["state"] = MachineState(data["state"])
        return cls(**data)


@dataclass
class StateMachineData:
    """Serializable state machine data."""

    id: str
    objective: str
    state: MachineState
    tasks: list[Task]
    checkpoints: list[Checkpoint]
    current_task_id: str | None
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "objective": self.objective,
            "state": self.state.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "current_task_id": self.current_task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "execution_history": self.execution_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            objective=data["objective"],
            state=MachineState(data["state"]),
            tasks=[Task.from_dict(t) for t in data["tasks"]],
            checkpoints=[Checkpoint.from_dict(c) for c in data["checkpoints"]],
            current_task_id=data.get("current_task_id"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            metadata=data.get("metadata", {}),
            execution_history=data.get("execution_history", []),
        )


class TaskStateMachine:
    """Persistent state machine for long-running multi-task objectives.

    Features:
    - Persistent state saved to disk (survives restarts)
    - Task dependency tracking
    - Checkpoint/resume capability
    - Hierarchical task decomposition
    - Execution history logging

    The machine transitions through states:
        UNINITIALIZED → PLANNING → EXECUTING → COMPLETED/FAILED
                                 ↔ PAUSED
    """

    def __init__(
        self,
        *,
        machine_id: str,
        state_dir: Path | None = None,
    ) -> None:
        """Initialize state machine.

        Args:
            machine_id: Unique identifier for this state machine instance
            state_dir: Directory for state persistence (default: .π/state)
        """
        self._state_dir = state_dir or (get_project_root() / STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / f"{machine_id}.json"

        now = datetime.now(UTC).isoformat()
        self._data = StateMachineData(
            id=machine_id,
            objective="",
            state=MachineState.UNINITIALIZED,
            tasks=[],
            checkpoints=[],
            current_task_id=None,
            created_at=now,
            updated_at=now,
        )

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    @classmethod
    def load_or_create(
        cls,
        machine_id: str,
        *,
        state_dir: Path | None = None,
    ) -> Self:
        """Load existing state machine or create new one.

        Args:
            machine_id: Unique identifier
            state_dir: Optional custom state directory

        Returns:
            TaskStateMachine instance (loaded or new)
        """
        state_dir = state_dir or (get_project_root() / STATE_DIR)
        state_file = state_dir / f"{machine_id}.json"

        if state_file.exists():
            logger.info("Loading existing state machine: %s", machine_id)
            return cls.load(state_file)

        logger.info("Creating new state machine: %s", machine_id)
        return cls(machine_id=machine_id, state_dir=state_dir)

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load state machine from file.

        Args:
            path: Path to state file

        Returns:
            Loaded TaskStateMachine instance
        """
        with path.open() as f:
            data = json.load(f)

        machine = cls(machine_id=data["id"], state_dir=path.parent)
        machine._data = StateMachineData.from_dict(data)
        logger.debug("Loaded state machine from %s", path)
        return machine

    def save(self) -> None:
        """Persist current state to disk."""
        self._data.updated_at = datetime.now(UTC).isoformat()
        with self._state_file.open("w") as f:
            json.dump(self._data.to_dict(), f, indent=2)
        logger.debug("Saved state machine to %s", self._state_file)

    def checkpoint(self, *, notes: str = "") -> Checkpoint:
        """Create a checkpoint of current state.

        Args:
            notes: Optional notes about this checkpoint

        Returns:
            Created Checkpoint object
        """
        checkpoint = Checkpoint(
            id=f"cp-{len(self._data.checkpoints) + 1}",
            timestamp=datetime.now(UTC).isoformat(),
            state=self._data.state,
            current_task_id=self._data.current_task_id,
            completed_task_ids=[
                t.id for t in self._data.tasks if t.status == TaskStatus.COMPLETED
            ],
            notes=notes,
        )
        self._data.checkpoints.append(checkpoint)
        self.save()
        logger.info("Created checkpoint: %s", checkpoint.id)
        return checkpoint

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        """Restore state to a previous checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to restore

        Raises:
            ValueError: If checkpoint not found
        """
        checkpoint = next(
            (c for c in self._data.checkpoints if c.id == checkpoint_id),
            None,
        )
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        # Reset non-completed tasks to pending
        for task in self._data.tasks:
            if task.id not in checkpoint.completed_task_ids:
                task.status = TaskStatus.PENDING
                task.result = None
                task.started_at = None
                task.completed_at = None

        self._data.state = checkpoint.state
        self._data.current_task_id = checkpoint.current_task_id
        self.save()
        logger.info("Restored to checkpoint: %s", checkpoint_id)

    # -------------------------------------------------------------------------
    # Objective & Task Management
    # -------------------------------------------------------------------------

    def set_objective(self, objective: str) -> None:
        """Set the ultimate objective for this state machine.

        Args:
            objective: The goal to accomplish
        """
        if self._data.state != MachineState.UNINITIALIZED:
            raise ValueError("Cannot change objective after initialization")

        self._data.objective = objective
        self._data.state = MachineState.PLANNING
        self._log_event("objective_set", {"objective": objective})
        self.save()

    def add_task(
        self,
        *,
        task_id: str,
        name: str,
        description: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: list[str] | None = None,
        parent_id: str | None = None,
        tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> Task:
        """Add a task to the state machine.

        Args:
            task_id: Unique identifier for the task
            name: Short name for the task
            description: Detailed description of what needs to be done
            priority: Task priority level
            dependencies: List of task IDs this depends on
            parent_id: Parent task ID for subtask hierarchy
            tags: Optional tags for categorization
            context: Task-specific context data

        Returns:
            Created Task object
        """
        if any(t.id == task_id for t in self._data.tasks):
            raise ValueError(f"Task ID already exists: {task_id}")

        task = Task(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            parent_id=parent_id,
            tags=tags or [],
            context=context or {},
        )
        self._data.tasks.append(task)
        self._log_event("task_added", {"task_id": task_id, "name": name})
        self.save()
        return task

    def decompose_goal(
        self,
        subtasks: list[dict[str, Any]],
    ) -> list[Task]:
        """Decompose the objective into subtasks.

        This is typically called after setting the objective to break it
        down into actionable steps.

        Args:
            subtasks: List of task definitions with keys:
                - id: Unique task ID
                - name: Task name
                - description: Task description
                - priority: Optional priority (default: NORMAL)
                - dependencies: Optional list of dependency task IDs
                - tags: Optional tags

        Returns:
            List of created Task objects
        """
        if self._data.state != MachineState.PLANNING:
            raise ValueError("Can only decompose during PLANNING state")

        created = []
        for subtask in subtasks:
            task = self.add_task(
                task_id=subtask["id"],
                name=subtask["name"],
                description=subtask["description"],
                priority=TaskPriority(subtask.get("priority", "normal")),
                dependencies=subtask.get("dependencies", []),
                tags=subtask.get("tags", []),
                context=subtask.get("context", {}),
            )
            created.append(task)

        self._data.state = MachineState.EXECUTING
        self._log_event("goal_decomposed", {"task_count": len(created)})
        self.save()
        return created

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return next((t for t in self._data.tasks if t.id == task_id), None)

    # -------------------------------------------------------------------------
    # Execution Control
    # -------------------------------------------------------------------------

    @property
    def state(self) -> MachineState:
        """Current machine state."""
        return self._data.state

    @property
    def objective(self) -> str:
        """The ultimate objective."""
        return self._data.objective

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        if not self._data.tasks:
            return False
        return all(t.is_terminal for t in self._data.tasks)

    @property
    def current_task(self) -> Task | None:
        """Get the current task being worked on."""
        if self._data.current_task_id:
            return self.get_task(self._data.current_task_id)
        return None

    @property
    def next_task(self) -> Task | None:
        """Get the next actionable task based on priority and dependencies.

        Returns the highest priority pending task whose dependencies are satisfied.
        """
        # Get all pending tasks
        pending = [t for t in self._data.tasks if t.status == TaskStatus.PENDING]
        if not pending:
            return None

        # Filter to tasks with satisfied dependencies
        actionable = []
        for task in pending:
            deps_satisfied = all(
                self.get_task(dep_id)
                and self.get_task(dep_id).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            if deps_satisfied:
                actionable.append(task)

        if not actionable:
            return None

        # Sort by priority (critical first) then by creation order
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
            TaskPriority.DEFERRED: 4,
        }
        actionable.sort(key=lambda t: (priority_order[t.priority], t.created_at))
        return actionable[0]

    def start_task(self, task_id: str | None = None) -> Task:
        """Start working on a task.

        Args:
            task_id: Specific task to start, or None to start next available

        Returns:
            The task that was started

        Raises:
            ValueError: If no task available or task not actionable
        """
        if self._data.state not in (MachineState.EXECUTING, MachineState.PAUSED):
            raise ValueError(f"Cannot start task in state: {self._data.state}")

        # If resuming from pause
        if self._data.state == MachineState.PAUSED:
            self._data.state = MachineState.EXECUTING

        if task_id:
            task = self.get_task(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            if not task.is_actionable:
                raise ValueError(
                    f"Task not actionable: {task_id} (status: {task.status})"
                )
        else:
            task = self.next_task
            if not task:
                raise ValueError("No actionable tasks available")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(UTC).isoformat()
        self._data.current_task_id = task.id
        self._log_event("task_started", {"task_id": task.id})
        self.save()
        return task

    def complete_current_task(
        self,
        result: TaskResult,
    ) -> Task:
        """Mark the current task as complete.

        Args:
            result: Result of the task execution

        Returns:
            The completed task

        Raises:
            ValueError: If no current task
        """
        task = self.current_task
        if not task:
            raise ValueError("No current task to complete")

        task.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        task.result = result
        task.completed_at = datetime.now(UTC).isoformat()

        self._log_event(
            "task_completed",
            {
                "task_id": task.id,
                "success": result.success,
                "duration": result.duration_seconds,
            },
        )

        # Clear current task
        self._data.current_task_id = None

        # Check if all done
        if self.is_complete:
            all_succeeded = all(
                t.status == TaskStatus.COMPLETED
                for t in self._data.tasks
                if t.status != TaskStatus.SKIPPED
            )
            self._data.state = (
                MachineState.COMPLETED if all_succeeded else MachineState.FAILED
            )
            self._log_event("machine_completed", {"success": all_succeeded})

        self.save()
        return task

    def fail_current_task(
        self,
        error: str,
        *,
        retry: bool = True,
    ) -> Task:
        """Mark the current task as failed.

        Args:
            error: Error message
            retry: Whether to retry the task (if retries remaining)

        Returns:
            The failed/retrying task
        """
        task = self.current_task
        if not task:
            raise ValueError("No current task to fail")

        task.retry_count += 1

        if retry and task.retry_count < task.max_retries:
            # Reset for retry
            task.status = TaskStatus.PENDING
            task.started_at = None
            self._log_event(
                "task_retry",
                {"task_id": task.id, "attempt": task.retry_count, "error": error},
            )
        else:
            # Mark as failed
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(UTC).isoformat()
            task.result = TaskResult(success=False, output="", error=error)
            self._log_event("task_failed", {"task_id": task.id, "error": error})

        self._data.current_task_id = None
        self.save()
        return task

    def pause(self, *, reason: str = "") -> None:
        """Pause execution.

        Args:
            reason: Optional reason for pausing
        """
        if self._data.state != MachineState.EXECUTING:
            raise ValueError(f"Cannot pause from state: {self._data.state}")

        self._data.state = MachineState.PAUSED
        self._log_event("machine_paused", {"reason": reason})
        self.checkpoint(notes=f"Paused: {reason}" if reason else "Manual pause")

    def resume(self) -> None:
        """Resume execution from paused state."""
        if self._data.state != MachineState.PAUSED:
            raise ValueError(f"Cannot resume from state: {self._data.state}")

        self._data.state = MachineState.EXECUTING
        self._log_event("machine_resumed", {})
        self.save()

    def skip_task(self, task_id: str, *, reason: str = "") -> Task:
        """Skip a task.

        Args:
            task_id: Task to skip
            reason: Reason for skipping

        Returns:
            The skipped task
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.SKIPPED
        task.completed_at = datetime.now(UTC).isoformat()
        task.result = TaskResult(success=True, output=f"Skipped: {reason}")
        self._log_event("task_skipped", {"task_id": task_id, "reason": reason})
        self.save()
        return task

    def block_task(self, task_id: str, *, reason: str) -> Task:
        """Mark a task as blocked.

        Args:
            task_id: Task to block
            reason: Reason for blocking

        Returns:
            The blocked task
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.BLOCKED
        task.context["blocked_reason"] = reason
        self._log_event("task_blocked", {"task_id": task_id, "reason": reason})
        self.save()
        return task

    def unblock_task(self, task_id: str) -> Task:
        """Unblock a blocked task.

        Args:
            task_id: Task to unblock

        Returns:
            The unblocked task
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if task.status != TaskStatus.BLOCKED:
            raise ValueError(f"Task not blocked: {task_id}")

        task.status = TaskStatus.PENDING
        task.context.pop("blocked_reason", None)
        self._log_event("task_unblocked", {"task_id": task_id})
        self.save()
        return task

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get_progress(self) -> dict[str, Any]:
        """Get progress summary.

        Returns:
            Dictionary with progress statistics
        """
        total = len(self._data.tasks)
        by_status = {}
        for task in self._data.tasks:
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1

        completed = by_status.get(TaskStatus.COMPLETED.value, 0)
        return {
            "total_tasks": total,
            "completed": completed,
            "pending": by_status.get(TaskStatus.PENDING.value, 0),
            "in_progress": by_status.get(TaskStatus.IN_PROGRESS.value, 0),
            "failed": by_status.get(TaskStatus.FAILED.value, 0),
            "blocked": by_status.get(TaskStatus.BLOCKED.value, 0),
            "skipped": by_status.get(TaskStatus.SKIPPED.value, 0),
            "percent_complete": (completed / total * 100) if total > 0 else 0,
            "state": self._data.state.value,
        }

    def get_completed_tasks(self) -> list[Task]:
        """Get all completed tasks."""
        return [t for t in self._data.tasks if t.status == TaskStatus.COMPLETED]

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return [t for t in self._data.tasks if t.status == TaskStatus.PENDING]

    def get_blocked_tasks(self) -> list[Task]:
        """Get all blocked tasks."""
        return [t for t in self._data.tasks if t.status == TaskStatus.BLOCKED]

    def get_failed_tasks(self) -> list[Task]:
        """Get all failed tasks."""
        return [t for t in self._data.tasks if t.status == TaskStatus.FAILED]

    def get_tasks_by_tag(self, tag: str) -> list[Task]:
        """Get tasks with a specific tag."""
        return [t for t in self._data.tasks if tag in t.tags]

    def get_execution_history(self) -> list[dict[str, Any]]:
        """Get the execution history log."""
        return self._data.execution_history.copy()

    def get_checkpoints(self) -> list[Checkpoint]:
        """Get all checkpoints."""
        return self._data.checkpoints.copy()

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event to execution history."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **data,
        }
        self._data.execution_history.append(event)
        logger.debug("Event: %s - %s", event_type, data)

    def __repr__(self) -> str:
        progress = self.get_progress()
        return (
            f"TaskStateMachine(id={self._data.id!r}, "
            f"state={self._data.state.value}, "
            f"progress={progress['percent_complete']:.0f}%)"
        )
