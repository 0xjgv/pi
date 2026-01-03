"""Minimal shared state for cross-module access without circular imports.

This module contains ONLY state management - no business logic.
Both workflow and support modules can safely import from here.
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.status import Status

# Current spinner status (if any) - used to pause during user prompts
_current_status: ContextVar["Status | None"] = ContextVar("status", default=None)


def get_current_status() -> "Status | None":
    """Get the current spinner status for suspension during user input."""
    return _current_status.get()


def set_current_status(status: "Status | None") -> None:
    """Set the current spinner status."""
    _current_status.set(status)
