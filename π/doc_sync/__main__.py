"""CLI entry point for documentation sync.

Usage:
    python -m π.doc_sync [--since-commit HASH] [--force]
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys

from π.config import Provider, Tier, get_lm
from π.doc_sync.core import DocSyncState, stage_doc_sync
from π.support.directory import get_project_root

logger = logging.getLogger(__name__)


def get_git_diff(since_commit: str | None = None) -> str:
    """Get git diff since commit or since last sync."""
    cmd = ["git", "diff", "--stat"]
    if since_commit:
        cmd.append(f"{since_commit}..HEAD")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=get_project_root(),
    )
    return result.stdout


def get_current_commit() -> str:
    """Get current HEAD commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        cwd=get_project_root(),
    )
    return result.stdout.strip()


def count_files_in_commit() -> int:
    """Count files changed in the most recent commit."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        cwd=get_project_root(),
    )
    return len([f for f in result.stdout.strip().split("\n") if f])


def read_claude_md() -> str:
    """Read current CLAUDE.md content."""
    claude_md = get_project_root() / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text()
    return ""


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Documentation sync agent")
    parser.add_argument(
        "--since-commit",
        help="Compare changes since this commit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync regardless of threshold",
    )
    parser.add_argument(
        "--accumulate-only",
        action="store_true",
        help="Only accumulate file count, don't run agent",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    state = DocSyncState.load()

    if args.accumulate_only:
        # Called by post-commit hook to track files
        files_in_commit = count_files_in_commit()
        state.files_changed_since_sync += files_in_commit
        state.save()
        logger.info(
            "Accumulated %d files (total: %d/%d)",
            files_in_commit,
            state.files_changed_since_sync,
            state.files_threshold,
        )
        return 0

    if not args.force and not state.should_trigger():
        logger.info(
            "Threshold not reached (%d/%d), skipping",
            state.files_changed_since_sync,
            state.files_threshold,
        )
        return 0

    # Get diff context
    since = args.since_commit or state.last_sync_commit
    git_diff = get_git_diff(since)
    current_claude_md = read_claude_md()

    if not git_diff.strip():
        logger.info("No changes to evaluate")
        return 0

    # Run agent (use MED tier - evaluation work, not heavy implementation)
    lm = get_lm(Provider.Claude, Tier.MED)
    result = stage_doc_sync(
        git_diff=git_diff,
        current_claude_md=current_claude_md,
        lm=lm,
    )

    if result.updated:
        state.mark_synced(get_current_commit())
        logger.info("Documentation synced successfully")
    else:
        logger.info("No documentation update performed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
