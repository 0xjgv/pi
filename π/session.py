"""Workflow session state management."""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent


class Command(StrEnum):
    """Workflow stage commands."""

    CLARIFY = "clarify"
    RESEARCH_CODEBASE = "research_codebase"
    CREATE_PLAN = "create_plan"
    IMPLEMENT_PLAN = "implement_plan"


def build_command_map(
    *,
    command_dir: Path = ROOT_DIR / ".claude/commands",
) -> dict[Command, str]:
    """Build a command map from the command directory."""
    command_map = {}
    if not command_dir.exists():
        return command_map

    for f in sorted(command_dir.glob("[0-9]_*.md")):
        try:
            # e.g., '1_research_codebase' -> 'RESEARCH_CODEBASE'
            command_name = f.stem.split("_", 1)[1].upper()
            if command_enum_member := getattr(Command, command_name, None):
                command_map[command_enum_member] = f"/{f.stem}"
        except (IndexError, AttributeError):
            logger.warning("Skipping malformed command file: %s", f.name)

    return command_map


COMMAND_MAP = build_command_map()


@dataclass
class WorkflowSession:
    """Encapsulates workflow session state and validation."""

    session_ids: dict[Command, str] = field(
        default_factory=lambda: {cmd: "" for cmd in Command}
    )
    input_doc_paths: dict[Command, str] = field(
        default_factory=lambda: {cmd: "" for cmd in Command}
    )

    def get_session_id(self, command: Command) -> str:
        """Get the session ID for a command."""
        return self.session_ids.get(command, "")

    def set_session_id(self, command: Command, session_id: str) -> None:
        """Set the session ID for a command."""
        self.session_ids[command] = session_id

    def get_doc_path(self, command: Command) -> str:
        """Get the document path for a command."""
        return self.input_doc_paths.get(command, "")

    def set_doc_path(self, command: Command, path: str) -> None:
        """Set the document path for a command."""
        self.input_doc_paths[command] = path

    def should_resume(self, command: Command, session_id: str | None) -> bool:
        """Check if we should resume a previous session.

        Returns True if the provided session_id matches the stored one.
        """
        if not session_id:
            return False
        return self.session_ids.get(command, "") == session_id

    def validate_plan_doc(self, plan_path: str) -> None:
        """Validate that plan_path is not the research document.

        Raises:
            ValueError: If the plan_path matches the research document used for create_plan.
        """
        research_doc = self.input_doc_paths.get(Command.CREATE_PLAN, "")
        if research_doc and plan_path == research_doc:
            raise ValueError(
                f"implement_plan requires the PLAN document, not the research document.\n"
                f"Received: {plan_path}\n"
                f"Hint: Use the plan document returned by create_plan."
            )

    def log_session_state(self) -> None:
        """Log all session IDs and input document paths for debugging."""
        logger.debug("WorkflowSession state:")
        logger.debug("Session IDs:")
        for command, session_id in self.session_ids.items():
            if session_id:
                logger.debug("  %s: %s", command.value, session_id)
            else:
                logger.debug("  %s: (not set)", command.value)
        logger.debug("Input document paths:")
        for command, doc_path in self.input_doc_paths.items():
            if doc_path:
                logger.debug("  %s: %s", command.value, doc_path)
            else:
                logger.debug("  %s: (not set)", command.value)
