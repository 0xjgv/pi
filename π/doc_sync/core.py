"""Documentation sync workflow stage.

Evaluates codebase changes and updates CLAUDE.md when warranted.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import dspy

from π.core import MAX_ITERS
from π.support.directory import get_project_root
from π.workflow.tools import ask_questions, write_claude_md

logger = logging.getLogger(__name__)

DOC_SYNC_STATE_FILE = ".π/doc-sync-state.json"
DEFAULT_FILES_THRESHOLD = 10


class DocSyncSignature(dspy.Signature):
    """Evaluate if documentation needs updating based on codebase changes.

    Analyze the git diff to determine if changes are significant enough
    to warrant a CLAUDE.md update. Consider:
    - New files or directories added
    - Changed build/test commands
    - New dependencies or tools
    - Architectural changes
    - Removed or renamed key components
    """

    git_diff: str = dspy.InputField(desc="Git diff since last documentation sync")
    current_claude_md: str = dspy.InputField(desc="Current CLAUDE.md content")

    needs_update: bool = dspy.OutputField(
        desc="True if CLAUDE.md should be updated to reflect changes"
    )
    update_rationale: str = dspy.OutputField(
        desc="Explanation of what needs updating and why, or why no update needed"
    )


@dataclass
class DocSyncResult:
    """Result from documentation sync evaluation."""

    needs_update: bool
    update_rationale: str
    updated: bool = False  # True if update was performed
    session_id: str | None = None


@dataclass
class DocSyncState:
    """Persistent state for documentation sync."""

    last_sync_commit: str | None = None
    last_sync_timestamp: str | None = None
    files_changed_since_sync: int = 0
    files_threshold: int = DEFAULT_FILES_THRESHOLD

    @classmethod
    def load(cls) -> DocSyncState:
        """Load state from file or return defaults."""
        state_path = get_project_root() / DOC_SYNC_STATE_FILE
        if not state_path.exists():
            return cls()
        try:
            data = json.loads(state_path.read_text())
            return cls(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to load doc sync state: %s", e)
            return cls()

    def save(self) -> None:
        """Persist state to file."""
        state_path = get_project_root() / DOC_SYNC_STATE_FILE
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {
                    "last_sync_commit": self.last_sync_commit,
                    "last_sync_timestamp": self.last_sync_timestamp,
                    "files_changed_since_sync": self.files_changed_since_sync,
                    "files_threshold": self.files_threshold,
                },
                indent=2,
            )
        )

    def mark_synced(self, commit_hash: str) -> None:
        """Mark current state as synced."""
        self.last_sync_commit = commit_hash
        self.last_sync_timestamp = datetime.now(UTC).isoformat()
        self.files_changed_since_sync = 0
        self.save()

    def should_trigger(self) -> bool:
        """Check if threshold reached for triggering sync."""
        return self.files_changed_since_sync >= self.files_threshold


def stage_doc_sync(
    *,
    git_diff: str,
    current_claude_md: str,
    lm: dspy.LM,
) -> DocSyncResult:
    """Evaluate and optionally update documentation.

    Uses a ReAct agent to:
    1. Analyze git diff for documentation-relevant changes
    2. If warranted, ask user for approval via HITL
    3. If approved, invoke write_claude_md with change context

    Args:
        git_diff: Git diff since last sync.
        current_claude_md: Current CLAUDE.md content.
        lm: DSPy language model for ReAct agent.

    Returns:
        DocSyncResult with evaluation outcome.
    """
    agent = dspy.ReAct(
        tools=[write_claude_md, ask_questions],
        signature=DocSyncSignature,
        max_iters=MAX_ITERS,
    )

    with dspy.context(lm=lm):
        result = agent(
            git_diff=git_diff,
            current_claude_md=current_claude_md,
        )

    logger.info(
        "DocSync evaluation: needs_update=%s, rationale=%s",
        result.needs_update,
        result.update_rationale[:100],
    )

    return DocSyncResult(
        needs_update=result.needs_update,
        update_rationale=result.update_rationale,
    )
