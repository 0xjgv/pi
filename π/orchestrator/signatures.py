"""DSPy signatures for orchestrator agent."""

from __future__ import annotations

import dspy


class OrchestratorSignature(dspy.Signature):
    """Orchestrate task decomposition and execution for an objective.

    Given an objective and current state, determine the next action:
    - Decompose into subtasks if needed
    - Execute tasks via appropriate workflow
    - Track completion until objective is done
    """

    objective: str = dspy.InputField(desc="The high-level objective to accomplish")
    state_summary: str = dspy.InputField(
        desc="Current state: completed tasks, pending tasks, iteration count"
    )

    next_action: str = dspy.OutputField(
        desc="Action to take: 'decompose', 'execute', 'complete', or 'halt'"
    )
    reasoning: str = dspy.OutputField(desc="Why this action was chosen")


class ComplexityAssessSignature(dspy.Signature):
    """Assess task complexity to route to appropriate workflow.

    Evaluate a task's complexity on a 0-100 scale:
    - 0-20: Trivial changes (typo fixes, simple additions)
    - 21-50: Moderate changes (single feature, clear implementation)
    - 51-100: Complex changes (multiple components, architectural decisions)
    """

    task_description: str = dspy.InputField(desc="The task to assess")
    codebase_context: str = dspy.InputField(
        desc="Relevant context about affected files/patterns"
    )

    complexity_score: int = dspy.OutputField(
        desc="0-100 scale: 0-20 = trivial (quick), 21-100 = complex (full workflow)"
    )
    rationale: str = dspy.OutputField(desc="Why this complexity score")


class OneThingSignature(dspy.Signature):
    """Determine the single next task to accomplish.

    Given an objective and completed work, identify the ONE most important
    thing that needs to happen next. Focus on incremental progress.
    """

    objective: str = dspy.InputField(desc="The high-level objective to accomplish")
    completed_tasks: str = dspy.InputField(
        desc="Summary of what has been completed so far"
    )
    pending_context: str = dspy.InputField(
        desc="Any known pending work or blockers"
    )

    next_task: str = dspy.OutputField(
        desc="The single next task to accomplish (atomic, actionable)"
    )
    rationale: str = dspy.OutputField(desc="Why this is the most important next step")
