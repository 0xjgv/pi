"""Minimal shared state for cross-module access without circular imports.

This module contains ONLY state management - no business logic.
Both workflow and support modules can safely import from here.
"""

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.status import Status

# Current spinner status (if any) - used to pause during user prompts
_current_status: ContextVar["Status | None"] = ContextVar("status", default=None)

# Flag to disable spinner when live display is active
_live_display_active: ContextVar[bool] = ContextVar("live_display", default=False)


def get_current_status() -> "Status | None":
    """Get the current spinner status for suspension during user input."""
    return _current_status.get()


def set_current_status(status: "Status | None") -> None:
    """Set the current spinner status."""
    _current_status.set(status)


def is_live_display_active() -> bool:
    """Check if live display is active (disables spinner)."""
    return _live_display_active.get()


def set_live_display_active(active: bool) -> None:
    """Set live display active flag."""
    _live_display_active.set(active)


# --- Artifact Event System ---


class ArtifactStatus(Enum):
    """Status of a tracked artifact."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ArtifactEvent:
    """Event emitted during workflow execution.

    Event types:
        - stage_start: A workflow stage has started
        - stage_end: A workflow stage has completed
        - phase_start: A workflow phase has started
        - phase_end: A workflow phase has completed
        - file_start: A file write operation has started
        - file_done: A file write operation completed successfully
        - file_failed: A file write operation failed
    """

    event_type: str
    path: str | None = None
    phase: str | None = None
    doc_type: str | None = None
    elapsed: float | None = None
    # Stage event fields
    stage: str | None = None  # "Research", "Design", "Execute"
    stage_index: int | None = None  # 1, 2, 3
    stage_total: int | None = None  # Total stages in workflow
    phase_count: int | None = None  # Phases in this stage


ArtifactListener = Callable[[ArtifactEvent], None]
_artifact_listeners: list[ArtifactListener] = []


def subscribe_to_artifacts(listener: ArtifactListener) -> Callable[[], None]:
    """Subscribe to artifact events.

    Args:
        listener: Callback function that receives ArtifactEvent objects.

    Returns:
        Unsubscribe function to remove the listener.
    """
    _artifact_listeners.append(listener)
    return lambda: _artifact_listeners.remove(listener)


def emit_artifact_event(event: ArtifactEvent) -> None:
    """Emit an artifact event to all subscribers."""
    for listener in _artifact_listeners:
        listener(event)
