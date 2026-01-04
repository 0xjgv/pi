"""Unified state machine for autonomous codebase ownership.

This module provides a persistent, human-editable state machine for executing
multi-phase objectives through research → plan → review → iterate → implement → commit.

Key features:
- YAML state file for human editing and intervention
- File locking for concurrent access safety
- Checkpoints for recovery
- Task dependencies and priorities
- Complexity-based workflow routing
- Validation with automatic retry

Example:
    >>> from π.machine import StateMachine
    >>> machine = StateMachine.load_or_create("feature-auth")
    >>> machine.set_objective("Implement user authentication with JWT")
    >>> machine.run()  # Autonomous execution with live display
"""

from π.machine.machine import StateMachine
from π.machine.state import (
    Checkpoint,
    MachineStatus,
    Task,
    TaskPriority,
    TaskStage,
    TaskStatus,
    WorkflowState,
)

__all__ = [
    "Checkpoint",
    "MachineStatus",
    "StateMachine",
    "Task",
    "TaskPriority",
    "TaskStage",
    "TaskStatus",
    "WorkflowState",
]
