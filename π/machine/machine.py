"""State machine execution engine.

Provides the core StateMachine class that orchestrates autonomous
workflow execution with human intervention support.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import dspy
from rich.console import Console

from π.config import Provider, get_lm
from π.machine.state import (
    Checkpoint,
    MachineStatus,
    Task,
    TaskPriority,
    TaskResult,
    TaskStage,
    TaskStatus,
    WorkflowState,
    WorkflowStrategy,
    get_state_path,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# DSPy Signatures
# -----------------------------------------------------------------------------


class DecomposeObjectiveSignature(dspy.Signature):
    """Decompose a high-level objective into concrete tasks.

    Break down the objective into specific, actionable tasks that follow
    the workflow: research → plan → review → iterate → implement → commit.

    Each task should be atomic and independently executable.
    """

    objective: str = dspy.InputField(desc="The high-level objective to accomplish")
    context: str = dspy.InputField(desc="Project context and any constraints")

    tasks: str = dspy.OutputField(
        desc=(
            "JSON array of tasks. Each task: "
            '{"id": "string", "description": "string", '
            '"priority": "critical|high|normal|low", '
            '"depends_on": ["task-ids"]}. '
            "Use meaningful IDs like 'research-auth', 'impl-login'."
        )
    )
    reasoning: str = dspy.OutputField(desc="Explanation of task breakdown")


class ComplexityAssessSignature(dspy.Signature):
    """Assess task complexity to determine workflow strategy.

    Score 0-100:
    - 0-20: Trivial (typo fix, simple addition) → quick workflow
    - 21-50: Moderate (single feature, clear path) → full workflow
    - 51-100: Complex (multi-component, architectural) → full workflow
    """

    task_description: str = dspy.InputField(desc="Task to assess")
    codebase_context: str = dspy.InputField(desc="Relevant codebase information")

    complexity_score: int = dspy.OutputField(desc="0-100 complexity score")
    rationale: str = dspy.OutputField(desc="Why this score")


class NextTaskSignature(dspy.Signature):
    """Determine the next task when no explicit tasks remain.

    Given the objective and completed work, identify what needs
    to happen next to make progress.
    """

    objective: str = dspy.InputField(desc="The high-level objective")
    completed_summary: str = dspy.InputField(desc="What has been done")
    pending_context: str = dspy.InputField(desc="Known pending work or blockers")

    next_task: str = dspy.OutputField(desc="Description of next task")
    task_id: str = dspy.OutputField(desc="Suggested ID for the task")
    rationale: str = dspy.OutputField(desc="Why this is the right next step")


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of implementation validation."""

    passed: bool
    failures: list[str]


def validate_implementation(project_root: Path | None = None) -> ValidationResult:
    """Run validation checks (make check + make test).

    Args:
        project_root: Root path for running commands.

    Returns:
        ValidationResult with pass status and failures.
    """
    failures: list[str] = []
    cwd = project_root or Path.cwd()

    # Type/lint check
    logger.info("Validating: make check")
    try:
        result = subprocess.run(
            ["make", "check"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            preview = (result.stderr or result.stdout)[:500]
            failures.append(f"Lint/type check failed: {preview}")
    except subprocess.TimeoutExpired:
        failures.append("Lint/type check timed out")
    except FileNotFoundError:
        logger.debug("make not found, skipping check")

    # Test suite
    logger.info("Validating: make test")
    try:
        result = subprocess.run(
            ["make", "test"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if result.returncode != 0:
            preview = (result.stderr or result.stdout)[:500]
            failures.append(f"Tests failed: {preview}")
    except subprocess.TimeoutExpired:
        failures.append("Tests timed out")
    except FileNotFoundError:
        logger.debug("make not found, skipping test")

    return ValidationResult(passed=len(failures) == 0, failures=failures)


# -----------------------------------------------------------------------------
# State Machine
# -----------------------------------------------------------------------------


class StateMachine:
    """Autonomous state machine for codebase ownership.

    Executes objectives through research → plan → review → iterate →
    implement → commit workflow with support for:

    - Human intervention via YAML state file editing
    - Checkpoints for recovery
    - Task dependencies and priorities
    - Complexity-based workflow routing
    - Validation with automatic retry

    Example:
        >>> machine = StateMachine.load_or_create("feature-auth")
        >>> machine.set_objective("Implement JWT authentication")
        >>> machine.add_task("research-auth", "Research existing auth patterns")
        >>> machine.run()
    """

    def __init__(
        self,
        state: WorkflowState,
        *,
        root: Path | None = None,
        console: Console | None = None,
    ) -> None:
        """Initialize state machine.

        Args:
            state: Workflow state to operate on.
            root: Project root for file operations.
            console: Rich console for output.
        """
        self._state = state
        self._root = root
        self._console = console or Console()

        # DSPy agents (lazy init)
        self._decompose_agent: dspy.ChainOfThought | None = None
        self._complexity_agent: dspy.ChainOfThought | None = None
        self._next_task_agent: dspy.ChainOfThought | None = None

    @classmethod
    def load_or_create(
        cls,
        machine_id: str,
        *,
        root: Path | None = None,
        console: Console | None = None,
    ) -> StateMachine:
        """Load existing machine or create new one.

        Args:
            machine_id: Unique identifier for this machine.
            root: Project root path.
            console: Rich console for output.

        Returns:
            StateMachine instance.
        """
        state = load_state(machine_id, root)
        if state is None:
            logger.info("Creating new state machine: %s", machine_id)
            state = WorkflowState(id=machine_id)
            save_state(state, root)
        else:
            logger.info("Loaded existing state machine: %s", machine_id)

        return cls(state, root=root, console=console)

    @classmethod
    def load(cls, machine_id: str, *, root: Path | None = None) -> StateMachine:
        """Load existing machine (raises if not found).

        Args:
            machine_id: Machine identifier.
            root: Project root path.

        Returns:
            StateMachine instance.

        Raises:
            FileNotFoundError: If no saved state exists.
        """
        state = load_state(machine_id, root)
        if state is None:
            raise FileNotFoundError(f"No state found for machine: {machine_id}")
        return cls(state, root=root)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Machine identifier."""
        return self._state.id

    @property
    def state(self) -> WorkflowState:
        """Current workflow state."""
        return self._state

    @property
    def status(self) -> MachineStatus:
        """Current machine status."""
        return self._state.status

    @property
    def objective(self) -> str:
        """Current objective."""
        return self._state.objective

    @property
    def current_task(self) -> Task | None:
        """Currently executing task."""
        if self._state.current_task_id:
            return self._state.get_task(self._state.current_task_id)
        return None

    @property
    def state_file_path(self) -> Path:
        """Path to the state YAML file."""
        return get_state_path(self._state.id, self._root)

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def set_objective(
        self,
        objective: str,
        *,
        issue_url: str = "",
        branch: str = "",
    ) -> None:
        """Set the objective for this machine.

        Args:
            objective: High-level goal to accomplish.
            issue_url: Optional GitHub issue URL.
            branch: Optional git branch for this work.
        """
        if self._state.status not in (MachineStatus.IDLE, MachineStatus.PAUSED):
            raise ValueError(f"Cannot set objective in status: {self._state.status}")

        self._state.objective = objective
        self._state.issue_url = issue_url
        self._state.branch = branch
        self._log_event("objective_set", {"objective": objective[:100]})
        self._save()

    def configure(self, **kwargs: Any) -> None:
        """Update machine configuration.

        Args:
            **kwargs: Configuration options (see MachineConfig).
        """
        for key, value in kwargs.items():
            if hasattr(self._state.config, key):
                setattr(self._state.config, key, value)
        self._save()

    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------

    def add_task(
        self,
        task_id: str,
        description: str,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        depends_on: list[str] | None = None,
        notes: str = "",
    ) -> Task:
        """Add a task to the machine.

        Args:
            task_id: Unique task identifier.
            description: What needs to be done.
            priority: Execution priority.
            depends_on: Task IDs this depends on.
            notes: Additional context.

        Returns:
            Created Task object.
        """
        if self._state.get_task(task_id):
            raise ValueError(f"Task ID already exists: {task_id}")

        task = Task(
            id=task_id,
            description=description,
            priority=priority,
            depends_on=depends_on or [],
            notes=notes,
        )
        self._state.tasks.append(task)
        self._log_event("task_added", {"task_id": task_id})
        self._save()
        return task

    def decompose_objective(self, *, context: str = "") -> list[Task]:
        """Use AI to decompose objective into tasks.

        Args:
            context: Additional context for planning.

        Returns:
            List of created tasks.
        """
        if not self._state.objective:
            raise ValueError("No objective set")

        logger.info("Decomposing objective into tasks...")
        agent = self._get_decompose_agent()
        lm = get_lm(Provider.Claude, "high")

        with dspy.context(lm=lm):
            result = agent(
                objective=self._state.objective,
                context=context or "No additional context.",
            )

        try:
            tasks_data = json.loads(result.tasks)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI returned invalid JSON: {e}") from e

        created = []
        for task_data in tasks_data:
            task = self.add_task(
                task_id=task_data["id"],
                description=task_data["description"],
                priority=TaskPriority(task_data.get("priority", "normal")),
                depends_on=task_data.get("depends_on", []),
            )
            created.append(task)

        logger.info("Created %d tasks", len(created))
        return created

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self._state.get_task(task_id)

    def update_task(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        notes: str | None = None,
    ) -> Task:
        """Update task properties.

        Args:
            task_id: Task to update.
            status: New status.
            priority: New priority.
            notes: New notes.

        Returns:
            Updated task.
        """
        task = self._state.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if notes is not None:
            task.notes = notes

        self._save()
        return task

    def skip_task(self, task_id: str, *, reason: str = "") -> Task:
        """Skip a task.

        Args:
            task_id: Task to skip.
            reason: Why it's being skipped.

        Returns:
            Skipped task.
        """
        task = self._state.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.SKIPPED
        task.completed_at = datetime.now(UTC).isoformat()
        task.result = TaskResult(success=True, output=f"Skipped: {reason}")
        self._log_event("task_skipped", {"task_id": task_id, "reason": reason})
        self._save()
        return task

    def block_task(self, task_id: str, *, reason: str) -> Task:
        """Block a task.

        Args:
            task_id: Task to block.
            reason: Why it's blocked.

        Returns:
            Blocked task.
        """
        task = self._state.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.BLOCKED
        task.blocked_reason = reason
        self._log_event("task_blocked", {"task_id": task_id, "reason": reason})
        self._save()
        return task

    def unblock_task(self, task_id: str) -> Task:
        """Unblock a task.

        Args:
            task_id: Task to unblock.

        Returns:
            Unblocked task.
        """
        task = self._state.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task.status = TaskStatus.PENDING
        task.blocked_reason = ""
        self._log_event("task_unblocked", {"task_id": task_id})
        self._save()
        return task

    # -------------------------------------------------------------------------
    # Execution Control
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Start or resume execution."""
        if self._state.status == MachineStatus.RUNNING:
            return

        if not self._state.objective:
            raise ValueError("No objective set")

        self._state.status = MachineStatus.RUNNING
        self._log_event("machine_started", {})
        self._save()

    def pause(self, *, reason: str = "") -> None:
        """Pause execution.

        Args:
            reason: Why execution is paused.
        """
        self._state.status = MachineStatus.PAUSED
        if reason:
            self._state.halt_reason = reason
        self._log_event("machine_paused", {"reason": reason})
        self.checkpoint(notes=f"Paused: {reason}" if reason else "Manual pause")

    def resume(self) -> None:
        """Resume from paused state."""
        if self._state.status != MachineStatus.PAUSED:
            raise ValueError(f"Cannot resume from: {self._state.status}")

        self._state.status = MachineStatus.RUNNING
        self._state.halt_reason = ""
        self._log_event("machine_resumed", {})
        self._save()

    def halt(self, *, reason: str) -> None:
        """Halt execution with failure.

        Args:
            reason: Why execution halted.
        """
        self._state.status = MachineStatus.FAILED
        self._state.halt_reason = reason
        self._log_event("machine_halted", {"reason": reason})
        self._save()

    # -------------------------------------------------------------------------
    # Checkpoints
    # -------------------------------------------------------------------------

    def checkpoint(self, *, notes: str = "") -> Checkpoint:
        """Create a checkpoint.

        Args:
            notes: Notes about this checkpoint.

        Returns:
            Created checkpoint.
        """
        cp = Checkpoint(
            id=f"cp-{len(self._state.checkpoints) + 1}",
            timestamp=datetime.now(UTC).isoformat(),
            machine_status=self._state.status,
            current_task_id=self._state.current_task_id,
            completed_task_ids=[
                t.id for t in self._state.tasks if t.status == TaskStatus.COMPLETED
            ],
            notes=notes,
        )
        self._state.checkpoints.append(cp)
        self._save()
        logger.info("Created checkpoint: %s", cp.id)
        return cp

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        """Restore to a checkpoint.

        Args:
            checkpoint_id: Checkpoint to restore.
        """
        cp = next(
            (c for c in self._state.checkpoints if c.id == checkpoint_id),
            None,
        )
        if not cp:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        # Reset non-completed tasks
        for task in self._state.tasks:
            if task.id not in cp.completed_task_ids:
                task.status = TaskStatus.PENDING
                task.stage = TaskStage.PENDING
                task.result = None
                task.started_at = None
                task.completed_at = None

        self._state.status = cp.machine_status
        self._state.current_task_id = cp.current_task_id
        self._log_event("checkpoint_restored", {"checkpoint_id": checkpoint_id})
        self._save()

    # -------------------------------------------------------------------------
    # Main Execution Loop
    # -------------------------------------------------------------------------

    def run(
        self,
        *,
        max_tasks: int | None = None,
        on_task_complete: Callable[[Task], None] | None = None,
    ) -> dict[str, Any]:
        """Run the state machine until complete or paused.

        Args:
            max_tasks: Maximum tasks to execute (None = unlimited).
            on_task_complete: Callback after each task.

        Returns:
            Execution summary.
        """
        self.start()
        tasks_run = 0

        while self._state.status == MachineStatus.RUNNING:
            # Check iteration limit
            if self._state.current_iteration >= self._state.config.max_iterations:
                self.halt(reason="Max iterations reached")
                break

            # Check task limit
            if max_tasks and tasks_run >= max_tasks:
                logger.info("Reached max tasks: %d", max_tasks)
                break

            # Reload state to pick up human edits
            self._reload_state()

            # Check if paused by human
            if self._state.status == MachineStatus.PAUSED:
                logger.info("Machine paused by human intervention")
                break

            # Get next task
            task = self._state.get_next_task()
            if not task:
                if self._state.is_complete():
                    self._state.status = MachineStatus.COMPLETED
                    self._log_event("machine_completed", {})
                    self._save()
                else:
                    # No actionable tasks - might need decomposition or blocked
                    blocked = [
                        t for t in self._state.tasks
                        if t.status == TaskStatus.BLOCKED
                    ]
                    if blocked:
                        self.pause(reason=f"{len(blocked)} tasks blocked")
                    else:
                        # Try to generate next task
                        self._generate_next_task()
                        if not self._state.get_next_task():
                            self._state.status = MachineStatus.COMPLETED
                            self._save()
                break

            # Execute task
            self._execute_task(task)
            tasks_run += 1
            self._state.current_iteration += 1

            if on_task_complete:
                on_task_complete(task)

            # Auto-checkpoint
            if self._state.config.auto_checkpoint:
                self.checkpoint(notes=f"After task: {task.id}")

        return {
            "tasks_run": tasks_run,
            "status": self._state.status.value,
            "progress": self._state.get_progress(),
            "is_complete": self._state.is_complete(),
        }

    def run_single_task(self, task_id: str) -> Task:
        """Execute a single specific task.

        Args:
            task_id: Task to execute.

        Returns:
            Executed task.
        """
        task = self._state.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        self._execute_task(task)
        return task

    def _execute_task(self, task: Task) -> None:
        """Execute a single task through the workflow.

        Args:
            task: Task to execute.
        """
        logger.info("Executing task [%s]: %s", task.id, task.description[:60])

        # Mark in progress
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(UTC).isoformat()
        self._state.current_task_id = task.id
        self._log_event("task_started", {"task_id": task.id})
        self._save()

        start_time = time.monotonic()

        try:
            # Assess complexity
            task.stage = TaskStage.ASSESSING
            self._save()
            complexity = self._assess_complexity(task)
            task.complexity_score = complexity

            # Route to workflow
            if complexity <= self._state.config.complexity_threshold:
                task.strategy = WorkflowStrategy.QUICK
                result = self._run_quick_workflow(task)
            else:
                task.strategy = WorkflowStrategy.FULL
                result = self._run_full_workflow(task)

            duration = time.monotonic() - start_time
            result.duration_seconds = duration

            # Validate if enabled
            if self._state.config.validate_changes and result.success:
                task.stage = TaskStage.VALIDATING
                self._save()
                validation = validate_implementation(self._root)

                if not validation.passed:
                    # Retry logic
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.status = TaskStatus.PENDING
                        task.stage = TaskStage.PENDING
                        failure_msg = "; ".join(validation.failures)
                        task.notes += f"\n\nRetry {task.retry_count}: {failure_msg}"
                        self._log_event(
                            "task_retry",
                            {"task_id": task.id, "failures": validation.failures},
                        )
                        self._save()
                        return
                    else:
                        result.success = False
                        failure_msg = "; ".join(validation.failures)
                        result.error = f"Validation failed: {failure_msg}"

            # Complete task
            task.result = result
            if result.success:
                task.status = TaskStatus.COMPLETED
                task.stage = TaskStage.COMPLETE
                self._log_event("task_completed", {"task_id": task.id})
            else:
                task.status = TaskStatus.FAILED
                self._log_event(
                    "task_failed",
                    {"task_id": task.id, "error": result.error},
                )
                if self._state.config.pause_on_failure:
                    self._state.status = MachineStatus.PAUSED
                    self._state.halt_reason = f"Task {task.id} failed"

            task.completed_at = datetime.now(UTC).isoformat()

        except Exception as e:
            logger.exception("Task execution failed: %s", task.id)
            task.status = TaskStatus.FAILED
            task.result = TaskResult(success=False, error=str(e))
            task.completed_at = datetime.now(UTC).isoformat()
            self._log_event("task_failed", {"task_id": task.id, "error": str(e)})

            if self._state.config.pause_on_failure:
                self._state.status = MachineStatus.PAUSED
                self._state.halt_reason = str(e)

        finally:
            self._state.current_task_id = None
            self._save()

    def _assess_complexity(self, task: Task) -> int:
        """Assess task complexity using LLM.

        Args:
            task: Task to assess.

        Returns:
            Complexity score 0-100.
        """
        logger.info("Assessing complexity for: %s", task.id)

        completed = "\n".join(
            f"- {t.description[:60]}"
            for t in self._state.get_completed_tasks()
        )
        context = (
            f"Objective: {self._state.objective}\n"
            f"Completed:\n{completed or 'None'}"
        )

        agent = self._get_complexity_agent()
        lm = get_lm(Provider.Claude, "high")

        with dspy.context(lm=lm):
            result = agent(
                task_description=task.description,
                codebase_context=context,
            )

        try:
            score = int(result.complexity_score)
            return max(0, min(100, score))
        except (ValueError, TypeError):
            logger.warning("Invalid complexity score, defaulting to 50")
            return 50

    def _run_quick_workflow(self, task: Task) -> TaskResult:
        """Run quick workflow (skip research/plan).

        Args:
            task: Task to execute.

        Returns:
            Task result.
        """
        logger.info("Running quick workflow for: %s", task.id)
        task.stage = TaskStage.IMPLEMENTING
        self._save()

        # Import here to avoid circular dependency
        from π.workflow.bridge import commit_changes, implement_plan

        try:
            # Direct implementation with task description as plan
            impl_result = implement_plan(task.description)

            task.stage = TaskStage.COMMITTING
            self._save()

            commit_result = commit_changes(task.description)
            task.commit_sha = commit_result.get("sha")

            return TaskResult(
                success=True,
                output=impl_result,
                artifacts=[task.commit_sha] if task.commit_sha else [],
            )
        except Exception as e:
            return TaskResult(success=False, error=str(e))

    def _run_full_workflow(self, task: Task) -> TaskResult:
        """Run full 6-stage workflow.

        Args:
            task: Task to execute.

        Returns:
            Task result.
        """
        logger.info("Running full workflow for: %s", task.id)

        from π.workflow.bridge import (
            commit_changes,
            create_plan,
            get_extracted_path,
            implement_plan,
            iterate_plan,
            research_codebase,
            review_plan,
        )

        try:
            # Stage 1: Research
            task.stage = TaskStage.RESEARCHING
            self._save()
            research_codebase(task.description)
            task.research_path = get_extracted_path("research")

            # Stage 2: Plan
            task.stage = TaskStage.PLANNING
            self._save()
            create_plan(task.description)
            task.plan_path = get_extracted_path("plan")

            # Stage 3: Review
            task.stage = TaskStage.REVIEWING
            self._save()
            review_result = review_plan(task.plan_path or "")

            # Stage 4: Iterate (if review suggests changes)
            if "suggest" in review_result.lower() or "improve" in review_result.lower():
                task.stage = TaskStage.ITERATING
                self._save()
                iterate_plan(task.plan_path or "", review_result)

            # Stage 5: Implement
            task.stage = TaskStage.IMPLEMENTING
            self._save()
            impl_result = implement_plan(task.plan_path or "")

            # Stage 6: Commit
            task.stage = TaskStage.COMMITTING
            self._save()
            commit_result = commit_changes(task.description)
            task.commit_sha = commit_result.get("sha")

            return TaskResult(
                success=True,
                output=impl_result,
                artifacts=[
                    p for p in [task.research_path, task.plan_path, task.commit_sha]
                    if p
                ],
            )
        except Exception as e:
            return TaskResult(success=False, error=str(e))

    def _generate_next_task(self) -> None:
        """Generate next task using AI when no explicit tasks remain."""
        logger.info("Generating next task...")

        completed = "\n".join(
            f"- [{t.id}] {t.description[:60]}"
            for t in self._state.get_completed_tasks()
        )
        pending = "\n".join(
            f"- [{t.id}] {t.description[:60]}"
            for t in self._state.get_pending_tasks()
        )

        agent = self._get_next_task_agent()
        lm = get_lm(Provider.Claude, "high")

        with dspy.context(lm=lm):
            result = agent(
                objective=self._state.objective,
                completed_summary=completed or "Nothing completed yet",
                pending_context=pending or "No pending tasks",
            )

        # Add the generated task
        self.add_task(
            task_id=result.task_id,
            description=result.next_task,
        )

    # -------------------------------------------------------------------------
    # Agents (lazy init)
    # -------------------------------------------------------------------------

    def _get_decompose_agent(self) -> dspy.ChainOfThought:
        if self._decompose_agent is None:
            self._decompose_agent = dspy.ChainOfThought(DecomposeObjectiveSignature)
        return self._decompose_agent

    def _get_complexity_agent(self) -> dspy.ChainOfThought:
        if self._complexity_agent is None:
            self._complexity_agent = dspy.ChainOfThought(ComplexityAssessSignature)
        return self._complexity_agent

    def _get_next_task_agent(self) -> dspy.ChainOfThought:
        if self._next_task_agent is None:
            self._next_task_agent = dspy.ChainOfThought(NextTaskSignature)
        return self._next_task_agent

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _save(self) -> None:
        """Save current state."""
        save_state(self._state, self._root)

    def _reload_state(self) -> None:
        """Reload state from disk (picks up human edits)."""
        reloaded = load_state(self._state.id, self._root)
        if reloaded:
            self._state = reloaded

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log event to execution history."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **data,
        }
        self._state.execution_log.append(event)
        logger.debug("Event: %s", event)

    # -------------------------------------------------------------------------
    # Status & Display
    # -------------------------------------------------------------------------

    def get_progress(self) -> dict[str, Any]:
        """Get progress summary."""
        return self._state.get_progress()

    def get_status_report(self) -> str:
        """Get human-readable status report."""
        progress = self.get_progress()
        lines = [
            f"Machine: {self._state.id}",
            f"Objective: {self._state.objective[:70]}...",
            f"Status: {self._state.status.value}",
            f"Progress: {progress['percent']:.0f}% "
            f"({progress['completed']}/{progress['total']})",
            "",
            "Tasks:",
        ]

        for task in self._state.tasks:
            status_icon = {
                TaskStatus.PENDING: "[ ]",
                TaskStatus.IN_PROGRESS: "[~]",
                TaskStatus.COMPLETED: "[x]",
                TaskStatus.FAILED: "[!]",
                TaskStatus.BLOCKED: "[B]",
                TaskStatus.SKIPPED: "[-]",
            }.get(task.status, "[ ]")

            lines.append(f"  {status_icon} [{task.id}] {task.description[:50]}")

        if self._state.halt_reason:
            lines.extend(["", f"Halt reason: {self._state.halt_reason}"])

        lines.extend(["", f"State file: {self.state_file_path}"])

        return "\n".join(lines)

    def __repr__(self) -> str:
        progress = self.get_progress()
        return (
            f"StateMachine(id={self._state.id!r}, "
            f"status={self._state.status.value}, "
            f"progress={progress['percent']:.0f}%)"
        )
