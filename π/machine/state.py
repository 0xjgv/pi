"""State models for the unified state machine.

Provides YAML-serializable state models designed for human editing.
The state file can be manually modified to:
- Add, edit, or remove tasks
- Change priorities and dependencies
- Add notes and comments
- Skip or block tasks
- Adjust configuration

File format is intentionally human-friendly YAML with comments preserved.
"""

from __future__ import annotations

import fcntl
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml

from π.support.directory import get_project_root

logger = logging.getLogger(__name__)

STATE_VERSION = 1
STATE_DIR = Path(".π/machines")


class TaskStatus(StrEnum):
    """Task execution status.

    Human-editable: Change status in YAML to control execution.
    - pending: Ready to execute (set to skip work)
    - in_progress: Currently executing (set by machine)
    - completed: Successfully finished
    - failed: Execution failed (can reset to pending to retry)
    - blocked: Waiting on external action (add blocked_reason)
    - skipped: Intentionally skipped (won't execute)
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskStage(StrEnum):
    """Granular execution stage within a task.

    Shows progress through the workflow phases.
    """

    PENDING = "pending"
    ASSESSING = "assessing"
    RESEARCHING = "researching"
    PLANNING = "planning"
    REVIEWING = "reviewing"
    ITERATING = "iterating"
    IMPLEMENTING = "implementing"
    COMMITTING = "committing"
    VALIDATING = "validating"
    COMPLETE = "complete"


class TaskPriority(StrEnum):
    """Task priority for execution ordering.

    Human-editable: Change priority to reorder execution.
    - critical: Execute first, blocks all others
    - high: Execute soon
    - normal: Standard priority
    - low: Execute when convenient
    - deferred: Execute last or skip for now
    """

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    DEFERRED = "deferred"


class MachineStatus(StrEnum):
    """Overall machine execution status.

    Human-editable: Set to 'paused' to stop execution.
    """

    IDLE = "idle"  # Not started
    RUNNING = "running"  # Actively executing
    PAUSED = "paused"  # Manually paused (edit to resume)
    COMPLETED = "completed"  # All tasks done
    FAILED = "failed"  # Halted on failure


class WorkflowStrategy(StrEnum):
    """Workflow execution strategy based on complexity."""

    QUICK = "quick"  # Simple change, skip research/plan
    FULL = "full"  # Full 6-stage workflow


@dataclass
class TaskResult:
    """Result of task execution."""

    success: bool
    output: str = ""
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**data)


@dataclass
class Task:
    """A single task in the workflow.

    Human-editable fields:
    - id: Unique identifier (use meaningful names like 'impl-auth')
    - description: What needs to be done
    - status: Change to 'skipped' to skip, 'pending' to retry
    - priority: Reorder execution
    - depends_on: Task IDs that must complete first
    - notes: Add context for the AI or yourself
    - blocked_reason: Why task is blocked (set status to 'blocked')
    """

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    stage: TaskStage = TaskStage.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    strategy: WorkflowStrategy | None = None
    depends_on: list[str] = field(default_factory=list)
    notes: str = ""  # Human notes for context
    blocked_reason: str = ""

    # Execution tracking
    complexity_score: int | None = None
    result: TaskResult | None = None
    retry_count: int = 0
    max_retries: int = 3

    # Artifacts produced
    research_path: str | None = None
    plan_path: str | None = None
    commit_sha: str | None = None

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, omitting None/empty values for cleaner YAML."""
        data: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
        }

        # Only include non-default values
        if self.stage != TaskStage.PENDING:
            data["stage"] = self.stage.value
        if self.priority != TaskPriority.NORMAL:
            data["priority"] = self.priority.value
        if self.strategy:
            data["strategy"] = self.strategy.value
        if self.depends_on:
            data["depends_on"] = self.depends_on
        if self.notes:
            data["notes"] = self.notes
        if self.blocked_reason:
            data["blocked_reason"] = self.blocked_reason
        if self.complexity_score is not None:
            data["complexity_score"] = self.complexity_score
        if self.result:
            data["result"] = self.result.to_dict()
        if self.retry_count > 0:
            data["retry_count"] = self.retry_count
        if self.max_retries != 3:
            data["max_retries"] = self.max_retries
        if self.research_path:
            data["research_path"] = self.research_path
        if self.plan_path:
            data["plan_path"] = self.plan_path
        if self.commit_sha:
            data["commit_sha"] = self.commit_sha
        if self.started_at:
            data["started_at"] = self.started_at
        if self.completed_at:
            data["completed_at"] = self.completed_at

        # Always include created_at
        data["created_at"] = self.created_at

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        result = None
        if data.get("result"):
            result = TaskResult.from_dict(data["result"])

        return cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus(data.get("status", "pending")),
            stage=TaskStage(data.get("stage", "pending")),
            priority=TaskPriority(data.get("priority", "normal")),
            strategy=(
                WorkflowStrategy(data["strategy"]) if data.get("strategy") else None
            ),
            depends_on=data.get("depends_on", []),
            notes=data.get("notes", ""),
            blocked_reason=data.get("blocked_reason", ""),
            complexity_score=data.get("complexity_score"),
            result=result,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            research_path=data.get("research_path"),
            plan_path=data.get("plan_path"),
            commit_sha=data.get("commit_sha"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    @property
    def is_actionable(self) -> bool:
        """Check if task can be executed."""
        return self.status == TaskStatus.PENDING

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a final state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
        )


@dataclass
class Checkpoint:
    """A recovery checkpoint.

    Checkpoints allow rolling back to a known good state.
    """

    id: str
    timestamp: str
    machine_status: MachineStatus
    current_task_id: str | None
    completed_task_ids: list[str]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "machine_status": self.machine_status.value,
            "current_task_id": self.current_task_id,
            "completed_task_ids": self.completed_task_ids,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            machine_status=MachineStatus(data["machine_status"]),
            current_task_id=data.get("current_task_id"),
            completed_task_ids=data.get("completed_task_ids", []),
            notes=data.get("notes", ""),
        )


@dataclass
class MachineConfig:
    """Machine configuration.

    Human-editable: Adjust these to control execution behavior.
    """

    max_iterations: int = 50  # Safety limit
    max_task_retries: int = 3  # Retries per task on validation failure
    complexity_threshold: int = 20  # Score ≤ this uses quick workflow
    auto_checkpoint: bool = True  # Checkpoint after each task
    pause_on_failure: bool = True  # Pause machine on task failure
    validate_changes: bool = True  # Run make check/test after implementation

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_task_retries": self.max_task_retries,
            "complexity_threshold": self.complexity_threshold,
            "auto_checkpoint": self.auto_checkpoint,
            "pause_on_failure": self.pause_on_failure,
            "validate_changes": self.validate_changes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            max_iterations=data.get("max_iterations", 50),
            max_task_retries=data.get("max_task_retries", 3),
            complexity_threshold=data.get("complexity_threshold", 20),
            auto_checkpoint=data.get("auto_checkpoint", True),
            pause_on_failure=data.get("pause_on_failure", True),
            validate_changes=data.get("validate_changes", True),
        )


@dataclass
class WorkflowState:
    """Complete state of a workflow execution.

    This is the root object serialized to YAML. The file is designed
    to be human-editable for intervention and correction.

    To intervene:
    1. Set status to 'paused' to stop execution
    2. Edit tasks: change status, priority, dependencies
    3. Add notes to provide context
    4. Set status back to 'running' to resume
    """

    # Identity
    id: str  # Machine ID (e.g., 'feature-auth')
    version: int = STATE_VERSION

    # Objective
    objective: str = ""
    issue_url: str = ""  # GitHub issue URL if applicable
    branch: str = ""  # Git branch for this work

    # Status
    status: MachineStatus = MachineStatus.IDLE
    halt_reason: str = ""
    current_iteration: int = 0

    # Configuration
    config: MachineConfig = field(default_factory=MachineConfig)

    # Tasks
    tasks: list[Task] = field(default_factory=list)
    current_task_id: str | None = None

    # History
    checkpoints: list[Checkpoint] = field(default_factory=list)
    execution_log: list[dict[str, Any]] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for YAML serialization."""
        return {
            "id": self.id,
            "version": self.version,
            "objective": self.objective,
            "issue_url": self.issue_url or None,
            "branch": self.branch or None,
            "status": self.status.value,
            "halt_reason": self.halt_reason or None,
            "current_iteration": self.current_iteration,
            "config": self.config.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
            "current_task_id": self.current_task_id,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "execution_log": self.execution_log[-50:],  # Keep last 50 entries
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            version=data.get("version", STATE_VERSION),
            objective=data.get("objective", ""),
            issue_url=data.get("issue_url") or "",
            branch=data.get("branch") or "",
            status=MachineStatus(data.get("status", "idle")),
            halt_reason=data.get("halt_reason") or "",
            current_iteration=data.get("current_iteration", 0),
            config=MachineConfig.from_dict(data.get("config", {})),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            current_task_id=data.get("current_task_id"),
            checkpoints=[Checkpoint.from_dict(c) for c in data.get("checkpoints", [])],
            execution_log=data.get("execution_log", []),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
        )

    # -------------------------------------------------------------------------
    # Task queries
    # -------------------------------------------------------------------------

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return next((t for t in self.tasks if t.id == task_id), None)

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def get_completed_tasks(self) -> list[Task]:
        """Get all completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def get_next_task(self) -> Task | None:
        """Get next actionable task based on priority and dependencies.

        Returns highest priority pending task whose dependencies are satisfied.
        """
        pending = self.get_pending_tasks()
        if not pending:
            return None

        # Filter to tasks with satisfied dependencies
        actionable = []
        completed_ids = {t.id for t in self.get_completed_tasks()}

        for task in pending:
            deps_satisfied = all(dep_id in completed_ids for dep_id in task.depends_on)
            if deps_satisfied:
                actionable.append(task)

        if not actionable:
            return None

        # Sort by priority (critical first), then by creation time
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
            TaskPriority.DEFERRED: 4,
        }
        actionable.sort(key=lambda t: (priority_order[t.priority], t.created_at))
        return actionable[0]

    def has_pending_work(self) -> bool:
        """Check if there's pending or in-progress work."""
        return any(
            t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
            for t in self.tasks
        )

    def is_complete(self) -> bool:
        """Check if all tasks are in terminal state."""
        if not self.tasks:
            return False
        return all(t.is_terminal for t in self.tasks)

    def get_progress(self) -> dict[str, Any]:
        """Get progress summary."""
        total = len(self.tasks)
        by_status: dict[str, int] = {}
        for task in self.tasks:
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1

        completed = by_status.get("completed", 0)
        return {
            "total": total,
            "completed": completed,
            "pending": by_status.get("pending", 0),
            "in_progress": by_status.get("in_progress", 0),
            "failed": by_status.get("failed", 0),
            "blocked": by_status.get("blocked", 0),
            "skipped": by_status.get("skipped", 0),
            "percent": (completed / total * 100) if total > 0 else 0,
        }


# -----------------------------------------------------------------------------
# YAML Serialization with Comments
# -----------------------------------------------------------------------------


YAML_HEADER = """\
# π State Machine - Human Editable
#
# This file tracks the state of an autonomous workflow. You can edit it to:
# - Add/remove/modify tasks
# - Change task priorities and dependencies
# - Add notes to guide the AI
# - Pause/resume execution by changing status
# - Skip tasks by setting status to 'skipped'
# - Retry failed tasks by setting status to 'pending'
#
# Status values: idle, running, paused, completed, failed
# Task status: pending, in_progress, completed, failed, blocked, skipped
# Priority: critical, high, normal, low, deferred
#
"""


def _represent_none(dumper: yaml.Dumper, _: None) -> yaml.Node:
    """Represent None as empty string for cleaner YAML."""
    return dumper.represent_scalar("tag:yaml.org,2002:null", "")


def _represent_str(dumper: yaml.Dumper, data: str) -> yaml.Node:
    """Use literal style for multiline strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


class StateDumper(yaml.SafeDumper):
    """Custom YAML dumper for cleaner output."""

    pass


StateDumper.add_representer(type(None), _represent_none)
StateDumper.add_representer(str, _represent_str)


def state_to_yaml(state: WorkflowState) -> str:
    """Serialize state to human-readable YAML."""
    data = state.to_dict()

    # Remove None values for cleaner output
    def clean_dict(d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: clean_dict(v) if isinstance(v, dict) else v
            for k, v in d.items()
            if v is not None
        }

    cleaned = clean_dict(data)
    yaml_content = yaml.dump(
        cleaned,
        Dumper=StateDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    return YAML_HEADER + yaml_content


def yaml_to_state(content: str) -> WorkflowState:
    """Parse YAML content to WorkflowState."""
    data = yaml.safe_load(content)
    return WorkflowState.from_dict(data)


# -----------------------------------------------------------------------------
# File Operations with Locking
# -----------------------------------------------------------------------------


def get_state_dir(root: Path | None = None) -> Path:
    """Get state directory, creating if needed."""
    root = root or get_project_root()
    state_dir = root / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_state_path(machine_id: str, root: Path | None = None) -> Path:
    """Get path to state file for machine ID."""
    # Sanitize machine_id for filesystem
    safe_id = re.sub(r"[^\w\-]", "_", machine_id)
    return get_state_dir(root) / f"{safe_id}.yaml"


def load_state(machine_id: str, root: Path | None = None) -> WorkflowState | None:
    """Load state from file with shared lock.

    Args:
        machine_id: Machine identifier.
        root: Project root path.

    Returns:
        WorkflowState if file exists and is valid, None otherwise.
    """
    state_path = get_state_path(machine_id, root)
    if not state_path.exists():
        logger.debug("State file not found: %s", state_path)
        return None

    try:
        with state_path.open() as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                content = f.read()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        state = yaml_to_state(content)
        logger.debug("Loaded state from %s", state_path)
        return state
    except (yaml.YAMLError, KeyError, ValueError) as e:
        logger.error("Failed to load state from %s: %s", state_path, e)
        return None


def save_state(state: WorkflowState, root: Path | None = None) -> None:
    """Save state to file atomically with exclusive lock.

    Uses temp file + rename for atomic writes.

    Args:
        state: Workflow state to save.
        root: Project root path.
    """
    state.updated_at = datetime.now(UTC).isoformat()
    state_path = get_state_path(state.id, root)
    temp_path = state_path.with_suffix(".yaml.tmp")

    try:
        content = state_to_yaml(state)

        with temp_path.open("w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(content)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        temp_path.rename(state_path)
        logger.debug("Saved state to %s", state_path)
    except OSError as e:
        logger.error("Failed to save state: %s", e)
        if temp_path.exists():
            temp_path.unlink()
        raise


def list_machines(root: Path | None = None) -> list[WorkflowState]:
    """List all saved state machines.

    Args:
        root: Project root path.

    Returns:
        List of WorkflowState instances, sorted by updated_at descending.
    """
    state_dir = get_state_dir(root)
    states = []

    for state_file in state_dir.glob("*.yaml"):
        if state_file.suffix == ".yaml" and not state_file.name.endswith(".tmp"):
            machine_id = state_file.stem
            state = load_state(machine_id, root)
            if state:
                states.append(state)

    states.sort(key=lambda s: s.updated_at, reverse=True)
    return states
