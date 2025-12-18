"""Workflow session state management."""

from dataclasses import dataclass, field
from enum import StrEnum


class Command(StrEnum):
    """Workflow stage commands."""

    RESEARCH = "research_codebase"
    PLAN = "create_plan"
    IMPLEMENT = "implement_plan"


COMMAND_MAP = {
    Command.RESEARCH: "/1_research_codebase",
    Command.PLAN: "/2_create_plan",
    Command.IMPLEMENT: "/3_implement_plan",
}


@dataclass
class WorkflowSession:
    """Encapsulates workflow session state and validation."""

    session_ids: dict[Command, str] = field(
        default_factory=lambda: {cmd: "" for cmd in Command}
    )
    doc_paths: dict[Command, str] = field(
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
        return self.doc_paths.get(command, "")

    def set_doc_path(self, command: Command, path: str) -> None:
        """Set the document path for a command."""
        self.doc_paths[command] = path

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
        research_doc = self.doc_paths.get(Command.PLAN, "")
        if research_doc and plan_path == research_doc:
            raise ValueError(
                f"implement_plan requires the PLAN document, not the research document.\n"
                f"Received: {plan_path}\n"
                f"Hint: Use the plan document returned by create_plan."
            )
