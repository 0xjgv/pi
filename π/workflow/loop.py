"""Iterative orchestration loop for multi-cycle workflow execution."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import dspy

from π.config import MAX_ITERS, Provider, Tier, get_lm
from π.workflow.bridge import research_codebase
from π.workflow.module import RPIWorkflow

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


@dataclass
class Task:
    """A discrete task extracted from the objective."""

    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
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

    tasks: str = dspy.OutputField(
        desc="JSON array of task objects with: id, description, dependencies, priority"
    )
    reasoning: str = dspy.OutputField(desc="Explanation of decomposition strategy")


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
    return {
        "id": task.id,
        "description": task.description,
        "dependencies": task.dependencies,
        "priority": task.priority,
        "status": task.status.value,
        "result": task.result,
        "error": task.error,
        "plan_doc_path": task.plan_doc_path,
        "research_doc_path": task.research_doc_path,
        "commit_hash": task.commit_hash,
    }


def _task_from_dict(data: dict[str, Any]) -> Task:
    """Deserialize Task from JSON."""
    return Task(
        id=data["id"],
        description=data["description"],
        dependencies=data.get("dependencies", []),
        priority=data.get("priority", 1),
        status=TaskStatus(data["status"]),
        result=data.get("result"),
        error=data.get("error"),
        plan_doc_path=data.get("plan_doc_path"),
        research_doc_path=data.get("research_doc_path"),
        commit_hash=data.get("commit_hash"),
    )


def save_state(state: LoopState, path: Path) -> None:
    """Persist loop state to disk with atomic write."""
    data = {
        "objective": state.objective,
        "iteration": state.iteration,
        "max_iterations": state.max_iterations,
        "status": state.status.value,
        "completed_task_ids": list(state.completed_task_ids),
        "tasks": [_task_to_dict(t) for t in state.tasks],
    }

    # Atomic write: write to temp file, then rename
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.rename(path)

    logger.debug("Saved state to %s", path)


def load_state(path: Path) -> LoopState:
    """Load previously saved loop state."""
    data = json.loads(path.read_text())

    tasks = [_task_from_dict(t) for t in data["tasks"]]

    return LoopState(
        objective=data["objective"],
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
    """Orchestration loop that executes RPIWorkflow to accomplish objectives."""

    _workflow: RPIWorkflow

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

        # Sub-modules
        self._workflow = RPIWorkflow(lm=self.lm)
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

        # Resume or start fresh
        if resume and state_path.exists():
            state = load_state(state_path)
            logger.info("Resumed from iteration %d", state.iteration)
        else:
            state = LoopState(objective=objective, max_iterations=self.max_iterations)
            state = self._decompose(state)
            save_state(state, state_path)

        with dspy.context(lm=self.lm):
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

                # 3. Execute RPIWorkflow on task
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

        new_tasks = self._parse_tasks(decomposed.tasks)

        if incremental:
            existing_ids = {t.id for t in state.tasks}
            for task in new_tasks:
                if task.id not in existing_ids:
                    state.tasks.append(task)
        else:
            state.tasks = new_tasks

        logger.info("Decomposed into %d tasks", len(state.tasks))
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
        """Execute RPIWorkflow on a single task."""
        # Build context for resumption
        resume_context = ""
        if task.status == TaskStatus.IN_PROGRESS and task.error:
            resume_context = (
                f"\n\nPrevious attempt failed with: {task.error}\n"
                "Check git status for any partial work and continue from there."
            )

        task_objective = f"""
Overall objective: {state.objective}

Current task: {task.description}

Previously completed tasks:
{self._format_completed_tasks(state)}
{resume_context}
Focus on completing this specific task while keeping the overall objective in mind.
"""
        result = self._workflow(objective=task_objective)

        # Store document paths
        task.plan_doc_path = result.plan_doc_path
        task.research_doc_path = result.research_doc_path

        return result

    def _update_state(
        self,
        state: LoopState,
        task: Task,
        result: dspy.Prediction,
    ) -> LoopState:
        """Update loop state after task execution."""
        # Extract results with null-safety
        impl_status = getattr(result, "implementation_status", None) or ""
        commit_result = getattr(result, "commit_result", None) or ""

        # Task completes only if implementation succeeded AND commit was made
        if "success" in impl_status.lower() and commit_result:
            task.status = TaskStatus.COMPLETED
            task.result = impl_status
            task.commit_hash = commit_result
            state.completed_task_ids.add(task.id)
            commit_preview = commit_result[:20]
            logger.info("Task %s completed with commit: %s", task.id, commit_preview)
        else:
            # Task stays in_progress for retry on resume
            task.error = impl_status or "Unknown error - no implementation status"
            logger.warning("Task %s did not complete successfully", task.id)

        return state

    def _evaluate_progress(self, state: LoopState) -> LoopState:
        """Evaluate overall progress toward objective."""
        pending = [
            _task_to_dict(t) for t in state.tasks if t.status == TaskStatus.PENDING
        ]
        evaluated = self._evaluator(
            objective=state.objective,
            completed_tasks=self._format_completed_tasks(state),
            pending_tasks=json.dumps(pending),
            codebase_state=self._get_codebase_context(),
        )

        if evaluated.is_complete:
            state.status = LoopStatus.COMPLETED
            logger.info("Objective completed!")

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

    def _parse_tasks(self, tasks_json: str) -> list[Task]:
        """Parse tasks from JSON output."""
        try:
            tasks_data = json.loads(tasks_json)
            return [
                Task(
                    id=t["id"],
                    description=t["description"],
                    dependencies=t.get("dependencies", []),
                    priority=t.get("priority", 1),
                )
                for t in tasks_data
            ]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse tasks: %s", e)
            return []
