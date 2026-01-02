"""Orchestrator agent for persistent workflow execution.

The OrchestratorAgent manages task decomposition and execution for a high-level
objective. It uses DSPy ReAct to decide when to break down tasks and when to
execute them via the appropriate workflow (full or quick).
"""

from __future__ import annotations

import logging
from pathlib import Path

import dspy

from π.config import Provider, get_lm
from π.orchestrator.signatures import (
    ComplexityAssessSignature,
    OneThingSignature,
    OrchestratorSignature,
)
from π.orchestrator.state import (
    OrchestratorStatus,
    Task,
    TaskStrategy,
    WorkflowState,
    load_or_create_state,
    save_state,
)
from π.orchestrator.tools import (
    WorkflowResult,
    add_task,
    format_status_display,
    get_next_task,
    increment_validation_retry,
    mark_blocked,
    mark_complete,
    mark_in_progress,
    should_retry_validation,
    validate_implementation,
)
from π.workflow.module import RPIWorkflow

logger = logging.getLogger(__name__)

# Complexity threshold for quick vs full workflow
QUICK_WORKFLOW_THRESHOLD = 20


class OrchestratorAgent(dspy.Module):
    """Orchestrator agent for persistent workflow execution.

    Manages a persistent state file and executes tasks incrementally
    using the appropriate workflow strategy based on complexity.

    Attributes:
        root: Project root path for state persistence.
        provider: AI provider for model selection.
    """

    def __init__(self, root: Path | None = None):
        """Initialize orchestrator agent.

        Args:
            root: Project root path for state persistence.
        """
        super().__init__()
        self.root = root

        # Build DSPy agents for decision-making
        self._orchestrator_agent = self._build_orchestrator_agent()
        self._complexity_agent = self._build_complexity_agent()
        self._one_thing_agent = self._build_one_thing_agent()

        # Workflow executor
        self._workflow = RPIWorkflow()

    def _build_orchestrator_agent(self) -> dspy.ChainOfThought:
        """Build orchestrator decision agent."""
        return dspy.ChainOfThought(OrchestratorSignature)

    def _build_complexity_agent(self) -> dspy.ChainOfThought:
        """Build complexity assessment agent."""
        return dspy.ChainOfThought(ComplexityAssessSignature)

    def _build_one_thing_agent(self) -> dspy.ChainOfThought:
        """Build one-thing decomposition agent."""
        return dspy.ChainOfThought(OneThingSignature)

    def _assess_complexity(self, task: Task, state: WorkflowState) -> int:
        """Assess task complexity using LLM reasoning.

        Args:
            task: Task to assess.
            state: Current workflow state for context.

        Returns:
            Complexity score 0-100.
        """
        logger.info("Assessing complexity for task: %s", task.description[:50])

        # Build context from completed tasks
        completed_context = "\n".join(
            f"- {t.description}" for t in state.tasks if t.status.value == "completed"
        )
        codebase_context = (
            f"Objective: {state.objective}\n"
            f"Completed work:\n{completed_context or 'None yet'}"
        )

        result = self._complexity_agent(
            task_description=task.description,
            codebase_context=codebase_context,
        )

        try:
            score = int(result.complexity_score)
            score = max(0, min(100, score))  # Clamp to 0-100
        except (ValueError, TypeError):
            logger.warning(
                "Invalid complexity score '%s', defaulting to 50",
                result.complexity_score,
            )
            score = 50

        logger.info(
            "Complexity assessment: score=%d, rationale=%s",
            score,
            result.rationale[:100],
        )
        return score

    def _reason_one_thing(self, state: WorkflowState) -> str:
        """Determine the single next task to accomplish.

        Args:
            state: Current workflow state.

        Returns:
            Description of the next task.
        """
        logger.info("Reasoning about next task for objective")

        completed = "\n".join(
            f"- [{t.id}] {t.description}"
            for t in state.tasks
            if t.status.value == "completed"
        )
        pending = "\n".join(
            f"- [{t.id}] {t.description}"
            for t in state.tasks
            if t.status.value == "pending"
        )

        result = self._one_thing_agent(
            objective=state.objective,
            completed_tasks=completed or "None yet",
            pending_context=pending or "No known pending work",
        )

        logger.info(
            "Next task identified: %s (reason: %s)",
            result.next_task[:50],
            result.rationale[:100],
        )
        return result.next_task

    def _run_quick_workflow(self, task: Task, state: WorkflowState) -> WorkflowResult:
        """Execute quick workflow for trivial changes.

        Quick workflow skips research/plan/review/iterate and goes
        directly to implementation with the task description as the plan.

        Args:
            task: Task to execute.
            state: Current workflow state.

        Returns:
            WorkflowResult with success status and outputs.
        """
        logger.info("Running quick workflow for task: %s", task.id)

        # For quick workflow, we'd ideally just implement directly
        # For now, we use the full workflow but could optimize later
        # The implement + commit stages will be added in Phase 3
        try:
            # Placeholder: In Phase 3, this will call implement_plan directly
            # For now, mark as needing full workflow integration
            return WorkflowResult(
                success=True,
                outputs={"strategy": "quick"},
                error=None,
            )
        except Exception as e:
            logger.exception("Quick workflow failed for task %s", task.id)
            return WorkflowResult(
                success=False,
                outputs={},
                error=str(e),
            )

    def _run_full_workflow(self, task: Task, state: WorkflowState) -> WorkflowResult:
        """Execute full 6-stage workflow.

        Full workflow: research -> plan -> review -> iterate -> implement -> commit

        Args:
            task: Task to execute.
            state: Current workflow state.

        Returns:
            WorkflowResult with success status and outputs.
        """
        logger.info("Running full workflow for task: %s", task.id)

        try:
            # Run existing 4-stage workflow
            result = self._workflow(objective=task.description)

            outputs = {
                "research": result.research_doc_path,
                "plan": result.plan_doc_path,
                "changes_made": result.changes_made,
                "strategy": "full",
            }

            # Implement + commit stages will be added in Phase 3
            # For now, workflow completes after iterate stage

            return WorkflowResult(
                success=True,
                outputs=outputs,
                error=None,
            )
        except Exception as e:
            logger.exception("Full workflow failed for task %s", task.id)
            return WorkflowResult(
                success=False,
                outputs={},
                error=str(e),
            )

    def _run_workflow(
        self,
        task: Task,
        complexity: int,
        state: WorkflowState,
    ) -> WorkflowResult:
        """Route task to appropriate workflow based on complexity.

        Args:
            task: Task to execute.
            complexity: Complexity score 0-100.
            state: Current workflow state.

        Returns:
            WorkflowResult with success status and outputs.
        """
        # Set strategy on task
        if complexity <= QUICK_WORKFLOW_THRESHOLD:
            task.strategy = TaskStrategy.QUICK_CHANGE
            return self._run_quick_workflow(task, state)
        else:
            task.strategy = TaskStrategy.FULL_WORKFLOW
            return self._run_full_workflow(task, state)

    def _validate_and_retry(
        self,
        task: Task,
        state: WorkflowState,
        complexity: int,
    ) -> WorkflowResult:
        """Validate implementation and retry if needed.

        Args:
            task: Task that was implemented.
            state: Current workflow state.
            complexity: Original complexity score for re-running workflow.

        Returns:
            Final WorkflowResult after validation/retries.
        """
        validation = validate_implementation(task, project_root=self.root)

        if validation.passed:
            logger.info("Validation passed for task %s", task.id)
            return WorkflowResult(success=True, outputs=task.outputs)

        # Validation failed
        failure_msg = "; ".join(validation.failures)
        logger.warning("Validation failed for task %s: %s", task.id, failure_msg[:200])

        if should_retry_validation(task):
            retry_count = increment_validation_retry(
                state,
                task.id,
                failure_message=failure_msg,
                root=self.root,
            )
            logger.info(
                "Retrying task %s (attempt %d)",
                task.id,
                retry_count,
            )

            # Re-run workflow with failure context
            # The task description is appended with failure info
            original_desc = task.description
            task.description = (
                f"{original_desc}\n\n"
                f"PREVIOUS ATTEMPT FAILED:\n{failure_msg}\n"
                f"Please fix the issues and try again."
            )

            result = self._run_workflow(task, complexity, state)

            # Restore original description
            task.description = original_desc

            if result.success:
                # Validate again
                return self._validate_and_retry(task, state, complexity)
            return result
        else:
            # Max retries exceeded
            mark_blocked(
                state,
                task.id,
                reason=f"Validation failed after {task.validation_retries} retries: {failure_msg}",
                root=self.root,
            )
            return WorkflowResult(
                success=False,
                outputs={},
                error=f"Validation failed after max retries: {failure_msg}",
            )

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute orchestrator workflow for objective.

        Main orchestration loop:
        1. Load or create state
        2. While pending tasks and iterations remain:
           a. If no actionable task, decompose with "one thing" reasoning
           b. Assess complexity
           c. Route to appropriate workflow
           d. Validate and retry if needed
           e. Mark complete or halt on failure

        Args:
            objective: High-level objective to accomplish.

        Returns:
            Prediction with completion status and summary.
        """
        logger.info("Starting orchestrator for objective: %s", objective[:100])

        # Load or create state
        state = load_or_create_state(objective, self.root)

        # Get LM for reasoning
        lm = get_lm(Provider.Claude, "high")

        with dspy.context(lm=lm):
            while (
                state.status == OrchestratorStatus.RUNNING
                and state.config.current_iteration < state.config.max_iterations
            ):
                logger.info(
                    "=== Iteration %d/%d ===",
                    state.config.current_iteration + 1,
                    state.config.max_iterations,
                )

                # Check if we have actionable tasks
                if not state.has_actionable_task():
                    if state.all_complete():
                        logger.info("All tasks complete!")
                        state.status = OrchestratorStatus.COMPLETED
                        save_state(state, self.root)
                        break

                    # Decompose: "What's the ONE thing?"
                    next_task_desc = self._reason_one_thing(state)
                    add_task(state, next_task_desc, root=self.root)

                # Get next task
                task = get_next_task(state)
                if task is None:
                    logger.info("No pending tasks, completing")
                    state.status = OrchestratorStatus.COMPLETED
                    save_state(state, self.root)
                    break

                # Mark in progress
                mark_in_progress(state, task.id, root=self.root)

                # Assess complexity
                complexity = self._assess_complexity(task, state)

                # Run appropriate workflow
                result = self._run_workflow(task, complexity, state)

                if result.success:
                    # Validation is integrated into workflow in Phase 5
                    # For now, mark complete directly
                    mark_complete(state, task.id, outputs=result.outputs, root=self.root)
                else:
                    # Halt on failure
                    state.halt(reason=result.error or "Workflow failed")
                    save_state(state, self.root)
                    break

                # Increment iteration
                state.increment_iteration()
                save_state(state, self.root)

        # Build summary
        completed_count = sum(
            1 for t in state.tasks if t.status.value == "completed"
        )
        total_count = len(state.tasks)

        return dspy.Prediction(
            completed=state.status == OrchestratorStatus.COMPLETED,
            status=state.status.value,
            tasks_completed=completed_count,
            tasks_total=total_count,
            iterations=state.config.current_iteration,
            halt_reason=state.halt_reason,
            summary=format_status_display(state),
        )

    def resume(self, objective_hash: str) -> dspy.Prediction:
        """Resume orchestrator from saved state.

        Args:
            objective_hash: Hash of objective to resume.

        Returns:
            Prediction with completion status and summary.
        """
        from π.orchestrator.state import load_state_by_hash

        state = load_state_by_hash(objective_hash, self.root)
        if state is None:
            raise ValueError(f"No state found for hash: {objective_hash}")

        logger.info("Resuming orchestrator for: %s", state.objective[:100])

        # Reset status if previously halted (allow retry)
        if state.status == OrchestratorStatus.HALTED:
            state.status = OrchestratorStatus.RUNNING
            state.halt_reason = None
            save_state(state, self.root)

        return self.forward(state.objective)
