"""Orchestrator state management for persistent workflow execution."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from π.support.directory import get_state_dir

logger = logging.getLogger(__name__)

STATE_VERSION = 1
DEFAULT_MAX_ITERATIONS = 50
DEFAULT_MAX_VALIDATION_RETRIES = 3


class TaskStatus(StrEnum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TaskStage(StrEnum):
    """Granular task execution stage for progress display."""

    PENDING = "pending"
    ASSESSING = "assessing complexity"
    RESEARCHING = "researching codebase"
    PLANNING = "creating plan"
    REVIEWING = "reviewing plan"
    ITERATING = "iterating on plan"
    IMPLEMENTING = "implementing changes"
    COMMITTING = "creating commit"
    VALIDATING = "validating changes"
    COMPLETE = "complete"


class OrchestratorStatus(StrEnum):
    """Orchestrator execution status."""

    RUNNING = "running"
    COMPLETED = "completed"
    HALTED = "halted"


class TaskStrategy(StrEnum):
    """Task execution strategy."""

    FULL_WORKFLOW = "full_workflow"
    QUICK_CHANGE = "quick_change"


@dataclass
class Task:
    """Individual task within the orchestrator workflow.

    Attributes:
        id: Unique task identifier (e.g., "t1", "t2").
        description: Human-readable task description.
        status: Current task status.
        stage: Current execution stage for progress display.
        parent_id: Optional parent task ID for subtask hierarchy.
        strategy: Execution strategy (full or quick workflow).
        outputs: Artifacts produced by this task.
        validation_retries: Number of validation retry attempts.
        last_validation_failure: Most recent validation failure message.
        started_at: ISO timestamp when task started.
        completed_at: ISO timestamp when task completed.
    """

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    stage: TaskStage = TaskStage.PENDING
    parent_id: str | None = None
    strategy: TaskStrategy | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    validation_retries: int = 0
    last_validation_failure: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, StrEnum) else self.status,
            "stage": self.stage.value if isinstance(self.stage, StrEnum) else self.stage,
            "parent_id": self.parent_id,
            "strategy": self.strategy.value if self.strategy else None,
            "outputs": self.outputs,
            "validation_retries": self.validation_retries,
            "last_validation_failure": self.last_validation_failure,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create Task from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus(data["status"]),
            stage=TaskStage(data["stage"]) if data.get("stage") else TaskStage.PENDING,
            parent_id=data.get("parent_id"),
            strategy=TaskStrategy(data["strategy"]) if data.get("strategy") else None,
            outputs=data.get("outputs", {}),
            validation_retries=data.get("validation_retries", 0),
            last_validation_failure=data.get("last_validation_failure"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class WorkflowConfig:
    """Configuration for orchestrator workflow.

    Attributes:
        max_iterations: Maximum iterations before halting.
        current_iteration: Current iteration count.
    """

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    current_iteration: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowConfig:
        """Create WorkflowConfig from dictionary."""
        return cls(
            max_iterations=data.get("max_iterations", DEFAULT_MAX_ITERATIONS),
            current_iteration=data.get("current_iteration", 0),
        )


@dataclass
class WorkflowState:
    """Persistent state for orchestrator workflow execution.

    Attributes:
        version: Schema version for migrations.
        objective: The high-level objective being accomplished.
        objective_hash: SHA256 hash of objective (truncated to 8 chars).
        created_at: ISO timestamp of state creation.
        updated_at: ISO timestamp of last update.
        config: Workflow configuration.
        status: Current orchestrator status.
        tasks: List of tasks in the workflow.
        halt_reason: Reason for halt if status is HALTED.
    """

    version: int
    objective: str
    objective_hash: str
    created_at: str
    updated_at: str
    config: WorkflowConfig
    status: OrchestratorStatus
    tasks: list[Task]
    halt_reason: str | None = None

    def has_pending_tasks(self) -> bool:
        """Check if there are pending or in-progress tasks."""
        return any(t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS) for t in self.tasks)

    def has_actionable_task(self) -> bool:
        """Check if there's a task ready to execute (pending)."""
        return any(t.status == TaskStatus.PENDING for t in self.tasks)

    def all_complete(self) -> bool:
        """Check if all tasks are completed."""
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks) if self.tasks else False

    def increment_iteration(self) -> None:
        """Increment current iteration count."""
        self.config.current_iteration += 1

    def halt(self, *, reason: str) -> None:
        """Halt orchestrator with reason."""
        self.status = OrchestratorStatus.HALTED
        self.halt_reason = reason

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "objective": self.objective,
            "objective_hash": self.objective_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config.to_dict(),
            "status": self.status.value if isinstance(self.status, StrEnum) else self.status,
            "tasks": [t.to_dict() for t in self.tasks],
            "halt_reason": self.halt_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowState:
        """Create WorkflowState from dictionary."""
        return cls(
            version=data["version"],
            objective=data["objective"],
            objective_hash=data["objective_hash"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            config=WorkflowConfig.from_dict(data["config"]),
            status=OrchestratorStatus(data["status"]),
            tasks=[Task.from_dict(t) for t in data["tasks"]],
            halt_reason=data.get("halt_reason"),
        )


def compute_objective_hash(objective: str) -> str:
    """Compute SHA256 hash of objective, truncated to 8 characters.

    Args:
        objective: The objective string to hash.

    Returns:
        8-character hex hash.
    """
    return hashlib.sha256(objective.encode()).hexdigest()[:8]


def get_state_path(objective: str, root: Path | None = None) -> Path:
    """Get path to state file for given objective.

    Args:
        objective: The objective string.
        root: Root path for state directory.

    Returns:
        Path to the state JSON file.
    """
    state_dir = get_state_dir(root)
    obj_hash = compute_objective_hash(objective)
    return state_dir / f"{obj_hash}.json"


def get_state_path_by_hash(obj_hash: str, root: Path | None = None) -> Path:
    """Get path to state file for given hash.

    Args:
        obj_hash: The objective hash.
        root: Root path for state directory.

    Returns:
        Path to the state JSON file.
    """
    state_dir = get_state_dir(root)
    return state_dir / f"{obj_hash}.json"


def create_state(objective: str) -> WorkflowState:
    """Create new workflow state for objective.

    Args:
        objective: The high-level objective.

    Returns:
        New WorkflowState instance.
    """
    now = datetime.now().isoformat()
    return WorkflowState(
        version=STATE_VERSION,
        objective=objective,
        objective_hash=compute_objective_hash(objective),
        created_at=now,
        updated_at=now,
        config=WorkflowConfig(),
        status=OrchestratorStatus.RUNNING,
        tasks=[],
    )


def load_state(objective: str, root: Path | None = None) -> WorkflowState | None:
    """Load state from file if it exists.

    Args:
        objective: The objective to load state for.
        root: Root path for state directory.

    Returns:
        WorkflowState if file exists and is valid, None otherwise.
    """
    state_path = get_state_path(objective, root)
    return _load_state_from_path(state_path)


def load_state_by_hash(obj_hash: str, root: Path | None = None) -> WorkflowState | None:
    """Load state from file by hash.

    Args:
        obj_hash: The objective hash.
        root: Root path for state directory.

    Returns:
        WorkflowState if file exists and is valid, None otherwise.
    """
    state_path = get_state_path_by_hash(obj_hash, root)
    return _load_state_from_path(state_path)


def _load_state_from_path(state_path: Path) -> WorkflowState | None:
    """Load state from specific path.

    Args:
        state_path: Path to state file.

    Returns:
        WorkflowState if file exists and is valid, None otherwise.
    """
    if not state_path.exists():
        logger.debug("State file not found: %s", state_path)
        return None

    try:
        with state_path.open() as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        state = WorkflowState.from_dict(data)
        logger.debug("Loaded state from %s", state_path)
        return state
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("Failed to load state from %s: %s", state_path, e)
        return None


def load_or_create_state(objective: str, root: Path | None = None) -> WorkflowState:
    """Load existing state or create new one.

    Args:
        objective: The objective to load/create state for.
        root: Root path for state directory.

    Returns:
        Existing or new WorkflowState.
    """
    state = load_state(objective, root)
    if state is None:
        state = create_state(objective)
        save_state(state, root)
        logger.info("Created new state for objective: %s", objective[:50])
    return state


def save_state(state: WorkflowState, root: Path | None = None) -> None:
    """Save state to file atomically.

    Uses temp file + rename for atomic writes.
    Acquires exclusive lock during write.

    Args:
        state: The workflow state to save.
        root: Root path for state directory.
    """
    state.updated_at = datetime.now().isoformat()
    state_path = get_state_path(state.objective, root)
    temp_path = state_path.with_suffix(".tmp")

    try:
        with temp_path.open("w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state.to_dict(), f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        temp_path.rename(state_path)
        logger.debug("Saved state to %s", state_path)
    except OSError as e:
        logger.error("Failed to save state: %s", e)
        if temp_path.exists():
            temp_path.unlink()
        raise


def list_states(root: Path | None = None) -> list[WorkflowState]:
    """List all saved workflow states.

    Args:
        root: Root path for state directory.

    Returns:
        List of WorkflowState instances.
    """
    state_dir = get_state_dir(root)
    states = []

    for state_file in state_dir.glob("*.json"):
        state = _load_state_from_path(state_file)
        if state:
            states.append(state)

    # Sort by updated_at descending (most recent first)
    states.sort(key=lambda s: s.updated_at, reverse=True)
    return states


def get_latest_state(root: Path | None = None) -> WorkflowState | None:
    """Get the most recently updated state.

    Args:
        root: Root path for state directory.

    Returns:
        Most recent WorkflowState or None if no states exist.
    """
    states = list_states(root)
    return states[0] if states else None
