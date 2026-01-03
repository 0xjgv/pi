"""Task Executor for State Machine Integration.

Bridges the TaskStateMachine with the RPIWorkflow to execute long-running
multi-phase objectives using Claude agents.

Example:
    >>> executor = TaskExecutor.create("scam-phone-app")
    >>> executor.set_objective(
    ...     "Build app for storing scamming phone numbers with user sync"
    ... )
    >>> executor.plan_tasks()  # AI decomposes into subtasks
    >>> executor.run_until_complete()  # Execute all tasks
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import dspy

from π.config import Provider, get_lm
from π.workflow.bridge import (
    ask_user_question,
    create_plan,
    get_extracted_path,
    iterate_plan,
    research_codebase,
    review_plan,
)
from π.workflow.state_machine import (
    MachineState,
    Task,
    TaskResult,
    TaskStateMachine,
    TaskStatus,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Task Planning Signature
# -----------------------------------------------------------------------------


class DecomposeObjectiveSignature(dspy.Signature):
    """Decompose a high-level objective into concrete, actionable tasks.

    Given an objective, break it down into specific tasks that can be
    executed sequentially. Consider dependencies between tasks.
    """

    objective: str = dspy.InputField(desc="The high-level objective to accomplish")
    context: str = dspy.InputField(
        desc="Additional context about the project or constraints"
    )

    tasks: str = dspy.OutputField(
        desc=(
            "JSON array of task objects. Each task has: "
            "id (string, e.g. 'task-1'), "
            "name (string, short name), "
            "description (string, detailed description), "
            "priority ('critical'|'high'|'normal'|'low'), "
            "dependencies (array of task IDs this depends on), "
            "tags (array of strings for categorization). "
            "Order tasks logically with proper dependencies."
        )
    )
    reasoning: str = dspy.OutputField(
        desc="Explanation of the task breakdown and dependency choices"
    )


class ExecuteTaskSignature(dspy.Signature):
    """Execute a specific task within the context of a larger objective.

    Use the available tools to accomplish the task. Report what was done
    and any artifacts created.
    """

    objective: str = dspy.InputField(desc="The overall objective being worked toward")
    task_name: str = dspy.InputField(desc="Name of the current task")
    task_description: str = dspy.InputField(desc="Detailed description of what to do")
    completed_tasks: str = dspy.InputField(
        desc="Summary of previously completed tasks and their outputs"
    )
    context: str = dspy.InputField(desc="Additional context or constraints")

    result: str = dspy.OutputField(desc="Description of what was accomplished")
    artifacts: str = dspy.OutputField(
        desc="Comma-separated list of files/paths created or modified"
    )
    next_steps: str = dspy.OutputField(
        desc="Suggested next steps or considerations for following tasks"
    )


# -----------------------------------------------------------------------------
# Task Executor
# -----------------------------------------------------------------------------


@dataclass
class ExecutorConfig:
    """Configuration for the task executor."""

    max_task_retries: int = 3
    checkpoint_interval: int = 1  # Checkpoint after every N completed tasks
    auto_checkpoint: bool = True
    pause_on_failure: bool = True  # Pause machine on task failure
    provider: Provider = Provider.Claude
    model_tier: str = "high"


class TaskExecutor:
    """Executes tasks from a TaskStateMachine using Claude agents.

    Provides:
    - Automatic task decomposition from objectives
    - Task execution with the full workflow toolkit
    - Progress tracking and checkpointing
    - Failure handling with retries
    """

    def __init__(
        self,
        machine: TaskStateMachine,
        *,
        config: ExecutorConfig | None = None,
    ):
        """Initialize executor.

        Args:
            machine: The state machine to execute tasks from
            config: Optional configuration
        """
        self.machine = machine
        self.config = config or ExecutorConfig()
        self._completed_since_checkpoint = 0

        # Build DSPy agents
        self._decompose_agent = self._build_decompose_agent()
        self._execute_agent = self._build_execute_agent()

    @classmethod
    def create(
        cls,
        machine_id: str,
        *,
        state_dir: Path | None = None,
        config: ExecutorConfig | None = None,
    ) -> "TaskExecutor":
        """Create a new executor with a fresh or loaded state machine.

        Args:
            machine_id: Unique ID for the state machine
            state_dir: Optional custom state directory
            config: Optional executor configuration

        Returns:
            TaskExecutor instance
        """
        machine = TaskStateMachine.load_or_create(machine_id, state_dir=state_dir)
        return cls(machine, config=config)

    @classmethod
    def resume(
        cls,
        machine_id: str,
        *,
        state_dir: Path | None = None,
        config: ExecutorConfig | None = None,
    ) -> "TaskExecutor":
        """Resume an existing executor from saved state.

        Args:
            machine_id: ID of the state machine to resume
            state_dir: Optional custom state directory
            config: Optional executor configuration

        Returns:
            TaskExecutor instance

        Raises:
            FileNotFoundError: If no saved state exists
        """
        machine = TaskStateMachine.load_or_create(machine_id, state_dir=state_dir)
        if machine.state == MachineState.UNINITIALIZED:
            raise FileNotFoundError(f"No saved state found for: {machine_id}")
        return cls(machine, config=config)

    # -------------------------------------------------------------------------
    # Agent Builders
    # -------------------------------------------------------------------------

    def _build_decompose_agent(self) -> dspy.ReAct:
        """Build agent for decomposing objectives into tasks."""
        return dspy.ReAct(
            signature=DecomposeObjectiveSignature,
            tools=[research_codebase, ask_user_question],
            max_iters=5,
        )

    def _build_execute_agent(self) -> dspy.ReAct:
        """Build agent for executing individual tasks."""
        return dspy.ReAct(
            signature=ExecuteTaskSignature,
            tools=[
                research_codebase,
                create_plan,
                review_plan,
                iterate_plan,
                ask_user_question,
            ],
            max_iters=10,
        )

    # -------------------------------------------------------------------------
    # Objective & Planning
    # -------------------------------------------------------------------------

    def set_objective(self, objective: str) -> None:
        """Set the objective for this executor.

        Args:
            objective: The high-level goal to accomplish
        """
        self.machine.set_objective(objective)
        logger.info("Objective set: %s", objective[:100])

    def plan_tasks(
        self,
        *,
        context: str = "",
        custom_tasks: list[dict[str, Any]] | None = None,
    ) -> list[Task]:
        """Plan tasks to accomplish the objective.

        Either uses AI to decompose the objective or accepts custom tasks.

        Args:
            context: Additional context for planning
            custom_tasks: Optional list of pre-defined tasks (skips AI planning)

        Returns:
            List of created Task objects
        """
        if custom_tasks:
            return self.machine.decompose_goal(custom_tasks)

        # Use AI to decompose
        logger.info("Decomposing objective into tasks...")
        lm = get_lm(self.config.provider, self.config.model_tier)

        with dspy.context(lm=lm):
            result = self._decompose_agent(
                objective=self.machine.objective,
                context=context or "No additional context provided.",
            )

        # Parse tasks from JSON output
        import json

        try:
            tasks_data = json.loads(result.tasks)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse task JSON: %s", e)
            raise ValueError(f"AI returned invalid task JSON: {e}") from e

        logger.info("Decomposed into %d tasks", len(tasks_data))
        logger.debug("Reasoning: %s", result.reasoning)

        return self.machine.decompose_goal(tasks_data)

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def execute_next_task(self) -> Task | None:
        """Execute the next available task.

        Returns:
            The completed task, or None if no tasks available
        """
        next_task = self.machine.next_task
        if not next_task:
            logger.info("No actionable tasks available")
            return None

        return self.execute_task(next_task.id)

    def execute_task(self, task_id: str) -> Task:
        """Execute a specific task.

        Args:
            task_id: ID of the task to execute

        Returns:
            The completed task
        """
        task = self.machine.start_task(task_id)
        logger.info("Starting task: %s - %s", task.id, task.name)

        try:
            result = self._run_task(task)
            task = self.machine.complete_current_task(result)

            # Auto-checkpoint
            self._completed_since_checkpoint += 1
            if (
                self.config.auto_checkpoint
                and self._completed_since_checkpoint >= self.config.checkpoint_interval
            ):
                self.machine.checkpoint(notes=f"After completing {task.name}")
                self._completed_since_checkpoint = 0

        except Exception as e:
            logger.exception("Task failed: %s", task.id)
            task = self.machine.fail_current_task(
                str(e),
                retry=task.retry_count < task.max_retries,
            )

            if self.config.pause_on_failure and task.status == TaskStatus.FAILED:
                self.machine.pause(reason=f"Task {task.id} failed: {e}")

        return task

    def _run_task(self, task: Task) -> TaskResult:
        """Run a task using the execute agent.

        Args:
            task: The task to run

        Returns:
            TaskResult with execution details
        """
        start_time = time.monotonic()

        # Build completed tasks summary
        completed = self.machine.get_completed_tasks()
        completed_summary = "\n".join(
            f"- {t.name}: {t.result.output[:200] if t.result else 'No output'}"
            for t in completed[-5:]  # Last 5 completed
        )
        if not completed_summary:
            completed_summary = "No tasks completed yet."

        # Build context from task
        context_parts = []
        if task.context:
            context_parts.append(f"Task context: {task.context}")
        if task.tags:
            context_parts.append(f"Tags: {', '.join(task.tags)}")
        context = (
            "\n".join(context_parts) if context_parts else "No additional context."
        )

        lm = get_lm(self.config.provider, self.config.model_tier)

        with dspy.context(lm=lm):
            result = self._execute_agent(
                objective=self.machine.objective,
                task_name=task.name,
                task_description=task.description,
                completed_tasks=completed_summary,
                context=context,
            )

        duration = time.monotonic() - start_time

        # Parse artifacts
        artifacts = (
            [a.strip() for a in result.artifacts.split(",") if a.strip()]
            if result.artifacts
            else []
        )

        return TaskResult(
            success=True,
            output=result.result,
            artifacts=artifacts,
            duration_seconds=duration,
            metadata={
                "next_steps": result.next_steps,
                "research_path": get_extracted_path("research"),
                "plan_path": get_extracted_path("plan"),
            },
        )

    def run_until_complete(
        self,
        *,
        max_tasks: int | None = None,
        on_task_complete: Callable[[Task], None] | None = None,
    ) -> dict[str, Any]:
        """Run tasks until the objective is complete or max reached.

        Args:
            max_tasks: Maximum number of tasks to run (None = unlimited)
            on_task_complete: Optional callback after each task completes

        Returns:
            Summary of execution
        """
        if self.machine.state == MachineState.PAUSED:
            logger.info("Resuming from paused state...")
            self.machine.resume()

        tasks_run = 0
        while not self.machine.is_complete:
            if max_tasks and tasks_run >= max_tasks:
                logger.info("Reached max tasks limit: %d", max_tasks)
                break

            task = self.execute_next_task()
            if not task:
                # No actionable tasks - might be blocked
                blocked = self.machine.get_blocked_tasks()
                if blocked:
                    logger.warning("Execution blocked by %d tasks", len(blocked))
                break

            tasks_run += 1

            if on_task_complete:
                on_task_complete(task)

            if self.machine.state == MachineState.PAUSED:
                logger.info("Execution paused")
                break

        # Final checkpoint
        self.machine.checkpoint(notes="Execution completed")

        return {
            "tasks_run": tasks_run,
            "progress": self.machine.get_progress(),
            "state": self.machine.state.value,
            "is_complete": self.machine.is_complete,
        }

    # -------------------------------------------------------------------------
    # Control
    # -------------------------------------------------------------------------

    def pause(self, *, reason: str = "") -> None:
        """Pause execution."""
        self.machine.pause(reason=reason)

    def resume_execution(self) -> None:
        """Resume execution from paused state."""
        self.machine.resume()

    def skip_task(self, task_id: str, *, reason: str = "") -> Task:
        """Skip a task."""
        return self.machine.skip_task(task_id, reason=reason)

    def get_progress(self) -> dict[str, Any]:
        """Get execution progress."""
        return self.machine.get_progress()

    def get_status_report(self) -> str:
        """Get a human-readable status report."""
        progress = self.get_progress()
        lines = [
            f"Objective: {self.machine.objective[:80]}...",
            f"State: {progress['state']}",
            f"Progress: {progress['percent_complete']:.0f}% ({progress['completed']}/{progress['total_tasks']} tasks)",
            "",
            "Task Status:",
            f"  - Completed: {progress['completed']}",
            f"  - Pending: {progress['pending']}",
            f"  - In Progress: {progress['in_progress']}",
            f"  - Failed: {progress['failed']}",
            f"  - Blocked: {progress['blocked']}",
        ]

        current = self.machine.current_task
        if current:
            lines.extend(
                [
                    "",
                    f"Current Task: {current.name}",
                    f"  {current.description[:100]}...",
                ]
            )

        next_task = self.machine.next_task
        if next_task and next_task != current:
            lines.extend(["", f"Next Task: {next_task.name}"])

        return "\n".join(lines)
