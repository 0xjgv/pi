"""Iterative orchestration loop for multi-cycle workflow execution."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import dspy
from pydantic import BaseModel, Field

from π.config import MAX_ITERS, Provider, Tier, get_lm
from π.workflow.context import _get_ctx
from π.workflow.orchestrator import StagedWorkflow
from π.workflow.tools import research_codebase

logger = logging.getLogger(__name__)

LOOP_STATE_DIR = Path(".π/loop-state")


class LoopStatus(StrEnum):
    """Status of the orchestration loop."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    """Status of an individual task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """A discrete task extracted from the objective."""

    id: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    priority: int = 1
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    plan_doc_path: str | None = None
    research_doc_path: str | None = None
    commit_hash: str | None = None  # Proof of completion


@dataclass
class LoopState:
    """Persistent state for the orchestration loop."""

    objective: str
    clarified_objective: str | None = None
    tasks: list[Task] = field(default_factory=list)
    completed_task_ids: set[str] = field(default_factory=set)
    iteration: int = 0
    max_iterations: int = 50
    status: LoopStatus = LoopStatus.RUNNING


# -----------------------------------------------------------------------------
# DSPy Signatures
# -----------------------------------------------------------------------------


class DecomposeSignature(dspy.Signature):
    """Decompose a high-level objective into discrete, implementable tasks."""

    objective: str = dspy.InputField(desc="The high-level objective to accomplish")
    codebase_context: str = dspy.InputField(desc="Current state of the codebase")
    completed_tasks: str = dspy.InputField(desc="Previously completed tasks (JSON)")

    tasks: list[Task] = dspy.OutputField(
        desc="List of task objects with id, description, dependencies, priority"
    )
    reasoning: str = dspy.OutputField(desc="Explanation of decomposition strategy")
    clarified_objective: str = dspy.OutputField(
        desc="The objective as understood after any user clarifications. "
        "If clarification was requested, reflect the clarified intent. "
        "If no clarification needed, return the original objective."
    )


class PrioritizerSignature(dspy.Signature):
    """Select the next best task to execute toward the objective."""

    objective: str = dspy.InputField(desc="The high-level objective")
    pending_tasks: str = dspy.InputField(desc="JSON array of pending tasks")
    completed_tasks: str = dspy.InputField(desc="JSON array of completed tasks")
    current_state: str = dspy.InputField(desc="Current codebase state summary")

    next_task_id: str = dspy.OutputField(desc="Selected task ID")
    rationale: str = dspy.OutputField(desc="Why this task was selected")


class EvaluatorSignature(dspy.Signature):
    """Evaluate progress toward the high-level objective."""

    objective: str = dspy.InputField(desc="The high-level objective")
    completed_tasks: str = dspy.InputField(desc="JSON array of completed tasks")
    pending_tasks: str = dspy.InputField(desc="JSON array of pending tasks")
    codebase_state: str = dspy.InputField(desc="Current codebase state")

    is_complete: bool = dspy.OutputField(desc="Whether objective is satisfied")
    completion_percentage: int = dspy.OutputField(desc="Estimated progress 0-100")
    remaining_work: str = dspy.OutputField(desc="Summary of remaining tasks")
    should_redecompose: bool = dspy.OutputField(desc="Whether to generate new tasks")


# -----------------------------------------------------------------------------
# State Persistence
# -----------------------------------------------------------------------------


def _objective_hash(objective: str) -> str:
    """Generate stable hash for objective to use as filename."""
    return hashlib.sha256(objective.encode()).hexdigest()[:12]


def _state_path(objective: str, checkpoint_dir: Path = LOOP_STATE_DIR) -> Path:
    """Get checkpoint file path for objective."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"{_objective_hash(objective)}.json"


def _task_to_dict(task: Task) -> dict[str, Any]:
    """Serialize Task for JSON storage."""
    data = task.model_dump()
    # Ensure enum is serialized as string value
    data["status"] = task.status.value
    return data


def _task_from_dict(data: dict[str, Any]) -> Task:
    """Deserialize Task from JSON."""
    return Task.model_validate(data)


def save_state(state: LoopState, path: Path) -> None:
    """Persist loop state to disk with atomic write."""
    now = datetime.now(UTC).isoformat()

    # Preserve created_at from existing file, or set it on first save
    created_at = now
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            created_at = existing.get("created_at", now)
        except (json.JSONDecodeError, OSError):
            pass  # Fall back to current timestamp

    data = {
        "objective": state.objective,
        "clarified_objective": state.clarified_objective,
        "iteration": state.iteration,
        "max_iterations": state.max_iterations,
        "status": state.status.value,
        "completed_task_ids": list(state.completed_task_ids),
        "tasks": [_task_to_dict(t) for t in state.tasks],
        "created_at": created_at,
        "updated_at": now,
    }

    # Atomic write: write to temp file, then rename
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.rename(path)

    logger.debug("Saved state to %s", path)


def load_state(path: Path) -> LoopState:
    """Load previously saved loop state."""
    data = json.loads(path.read_text(encoding="utf-8"))

    tasks = [_task_from_dict(t) for t in data["tasks"]]

    return LoopState(
        objective=data["objective"],
        clarified_objective=data.get("clarified_objective"),
        tasks=tasks,
        completed_task_ids=set(data["completed_task_ids"]),
        iteration=data["iteration"],
        max_iterations=data["max_iterations"],
        status=LoopStatus(data["status"]),
    )


def archive_state(path: Path, checkpoint_dir: Path = LOOP_STATE_DIR) -> None:
    """Move completed state to archive directory."""
    archive_dir = checkpoint_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    path.rename(archive_dir / path.name)
    logger.info("Archived state to %s", archive_dir / path.name)


# -----------------------------------------------------------------------------
# ObjectiveLoop
# -----------------------------------------------------------------------------


class ObjectiveLoop(dspy.Module):
    """Orchestration loop that executes StagedWorkflow to accomplish objectives."""

    _workflow: StagedWorkflow

    def __init__(
        self,
        *,
        lm: dspy.LM | None = None,
        max_iterations: int = 50,
        checkpoint_dir: Path = LOOP_STATE_DIR,
    ) -> None:
        super().__init__()

        self.lm = lm or get_lm(Provider.Claude, Tier.HIGH)
        self.max_iterations = max_iterations
        self.checkpoint_dir = checkpoint_dir

        # Configure JSONAdapter for typed outputs
        dspy.configure(adapter=dspy.JSONAdapter())

        # Sub-modules
        self._workflow = StagedWorkflow(lm=self.lm)
        self._decomposer = dspy.ReAct(
            signature=DecomposeSignature,
            tools=[research_codebase],
            max_iters=MAX_ITERS,
        )
        self._prioritizer = dspy.ChainOfThought(PrioritizerSignature)
        self._evaluator = dspy.ChainOfThought(EvaluatorSignature)

    def forward(self, objective: str, *, resume: bool = True) -> LoopState:
        """Execute the orchestration loop until objective is complete."""
        state_path = _state_path(objective, self.checkpoint_dir)

        with dspy.context(lm=self.lm):
            # Resume or start fresh
            if resume and state_path.exists():
                state = load_state(state_path)
                logger.info("Resumed from iteration %d", state.iteration)
            else:
                state = LoopState(
                    objective=objective, max_iterations=self.max_iterations
                )
                state = self._decompose(state)
                save_state(state, state_path)

                # Early exit if decomposition failed
                if state.status == LoopStatus.FAILED:
                    logger.error("Initial decomposition failed, exiting")
                    return state

            while self._should_continue(state):
                state.iteration += 1
                logger.info("=== LOOP ITERATION %d ===", state.iteration)

                # 1. Select next task
                task = self._select_next_task(state)
                if task is None:
                    state = self._handle_no_tasks(state)
                    continue

                # 2. Checkpoint BEFORE execution (crash recovery)
                task.status = TaskStatus.IN_PROGRESS
                save_state(state, state_path)

                # 3. Execute StagedWorkflow on task
                try:
                    result = self._execute_task(task, state)
                    state = self._update_state(state, task, result)
                except Exception as e:
                    task.error = str(e)
                    logger.error("Task %s failed: %s", task.id, e)
                    # Task stays IN_PROGRESS for retry on resume

                # 4. Evaluate progress
                state = self._evaluate_progress(state)

                # 5. Re-decompose if needed
                if self._should_redecompose(state):
                    state = self._decompose(state, incremental=True)

                # 6. Checkpoint AFTER execution
                save_state(state, state_path)

        # Archive on completion
        if state.status == LoopStatus.COMPLETED:
            archive_state(state_path, self.checkpoint_dir)

        return state

    def _decompose(self, state: LoopState, *, incremental: bool = False) -> LoopState:
        """Decompose objective into tasks."""
        codebase_context = self._get_codebase_context()
        completed_summary = self._format_completed_tasks(state)

        decomposed = self._decomposer(
            objective=state.objective,
            codebase_context=codebase_context,
            completed_tasks=completed_summary,
        )

        # Extract clarified objective (fallback to original)
        clarified = getattr(decomposed, "clarified_objective", None) or state.objective
        state.clarified_objective = clarified

        if clarified != state.objective:
            truncated = clarified[:60] + "..." if len(clarified) > 60 else clarified
            logger.info("Objective clarified: %s", truncated)

        # Direct access - typed as list[Task] via JSONAdapter
        new_tasks = decomposed.tasks

        if not new_tasks:
            logger.error("Decomposition returned no tasks")
            state.status = LoopStatus.FAILED
            return state

        if incremental:
            existing_ids = {t.id for t in state.tasks}
            for task in new_tasks:
                if task.id not in existing_ids:
                    state.tasks.append(task)
        else:
            state.tasks = list(new_tasks)

        logger.info("Decomposed into %d tasks", len(state.tasks))

        # Display task count and list to user
        task_count = len(state.tasks)
        prefix = "Re-identified" if incremental else "Identified"
        print(f"\n{prefix} {task_count} task{'s' if task_count != 1 else ''}:")
        for i, task in enumerate(state.tasks, 1):
            status_marker = "✓" if task.status == TaskStatus.COMPLETED else " "
            print(f"  {status_marker} {i}. {task.description}")

        return state

    def _select_next_task(self, state: LoopState) -> Task | None:
        """Select the next task to execute."""
        # Filter executable tasks (pending + dependencies satisfied)
        executable = [
            t
            for t in state.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in state.completed_task_ids for dep in t.dependencies)
        ]

        # Also include in_progress tasks (for retry after crash)
        in_progress = [t for t in state.tasks if t.status == TaskStatus.IN_PROGRESS]
        if in_progress:
            logger.info("Resuming in_progress task: %s", in_progress[0].id)
            return in_progress[0]

        if not executable:
            return None

        # Use prioritizer to select best task
        prioritized = self._prioritizer(
            objective=state.objective,
            pending_tasks=json.dumps([_task_to_dict(t) for t in executable]),
            completed_tasks=self._format_completed_tasks(state),
            current_state=self._get_codebase_context(),
        )

        # Find selected task
        selected_id = prioritized.next_task_id.strip()
        return next((t for t in executable if t.id == selected_id), executable[0])

    def _execute_task(self, task: Task, state: LoopState) -> dspy.Prediction:
        """Execute StagedWorkflow on a single task."""
        # Clear session context for fresh task isolation
        _get_ctx().session_ids.clear()

        # Build context for resumption
        resume_context = ""
        if task.status == TaskStatus.IN_PROGRESS and task.error:
            resume_context = (
                f"\n\nPrevious attempt failed with: {task.error}\n"
                "Check git status for any partial work and continue from there."
            )

        # Use clarified objective if available
        effective_objective = state.clarified_objective or state.objective

        task_objective = f"""
Overall objective: {effective_objective}

Current task: {task.description}

Previously completed tasks:
{self._format_completed_tasks(state)}
{resume_context}
Focus on completing this specific task while keeping the overall objective in mind.
"""
        result = self._workflow(objective=task_objective)

        # Store document paths (may not exist for early-exit)
        task.plan_doc_path = getattr(result, "plan_doc_path", None)
        task.research_doc_path = getattr(result, "research_doc_path", None)

        return result

    def _update_state(
        self,
        state: LoopState,
        task: Task,
        result: dspy.Prediction,
    ) -> LoopState:
        """Update loop state after task execution."""
        # Extract StagedWorkflow results with null-safety
        status = getattr(result, "status", None) or ""
        commit_hash = getattr(result, "commit_hash", None)
        reason = getattr(result, "reason", None)

        # Task completes if status indicates success (with or without commit)
        if status in ("success", "already_complete"):
            task.status = TaskStatus.COMPLETED
            task.result = reason or status
            task.commit_hash = commit_hash  # May be None for early-exit
            state.completed_task_ids.add(task.id)
            if commit_hash:
                short_hash = commit_hash[:20]
                logger.info("Task %s completed with commit: %s", task.id, short_hash)
            else:
                logger.info("Task %s completed (no commit needed): %s", task.id, reason)
        else:
            # Task stays in_progress for retry on resume
            task.error = reason or f"Task failed with status: {status}"
            logger.warning("Task %s did not complete: %s", task.id, task.error)

        return state

    def _evaluate_progress(self, state: LoopState) -> LoopState:
        """Evaluate progress and determine if redecomposition is needed."""
        pending = [
            _task_to_dict(t) for t in state.tasks if t.status == TaskStatus.PENDING
        ]
        evaluated = self._evaluator(
            objective=state.objective,
            completed_tasks=self._format_completed_tasks(state),
            pending_tasks=json.dumps(pending),
            codebase_state=self._get_codebase_context(),
        )

        # Log progress but don't set completion here - let task selection drive that
        if evaluated.is_complete:
            logger.info(
                "Evaluator suggests objective met (progress: %d%%)",
                evaluated.completion_percentage,
            )

        return state

    def _should_continue(self, state: LoopState) -> bool:
        """Determine if the loop should continue."""
        if state.status != LoopStatus.RUNNING:
            return False
        if state.iteration >= state.max_iterations:
            logger.warning("Max iterations (%d) reached", state.max_iterations)
            state.status = LoopStatus.FAILED
            return False
        return True

    def _should_redecompose(self, state: LoopState) -> bool:
        """Check if we should generate new tasks."""
        # Simple heuristic: redecompose if all tasks done but not complete
        all_done = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in state.tasks
        )
        return all_done and state.status == LoopStatus.RUNNING

    def _handle_no_tasks(self, state: LoopState) -> LoopState:
        """Handle case when no executable tasks are available."""
        pending = [t for t in state.tasks if t.status == TaskStatus.PENDING]
        if not pending:
            state.status = LoopStatus.COMPLETED
            logger.info("All tasks completed")
        else:
            logger.warning("No executable tasks - blocked by dependencies")
            state = self._decompose(state, incremental=True)
        return state

    def _get_codebase_context(self) -> str:
        """Get current codebase state summary via git."""
        try:
            # Get git status for context
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            status = result.stdout.strip() or "(clean)"

            # Get recent commits
            result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            recent_commits = result.stdout.strip()

            return f"Git status:\n{status}\n\nRecent commits:\n{recent_commits}"
        except Exception as e:
            logger.warning("Failed to get git context: %s", e)
            return "(unable to get git context)"

    def _format_completed_tasks(self, state: LoopState) -> str:
        """Format completed tasks for context."""
        completed = [t for t in state.tasks if t.status == TaskStatus.COMPLETED]
        return json.dumps([_task_to_dict(t) for t in completed])
