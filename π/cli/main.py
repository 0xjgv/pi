"""CLI entry point for the π workflow agent."""

import argparse
import logging
import sys
from importlib.metadata import version as get_version

from dotenv import load_dotenv

from π.core import Provider, Tier, get_lm
from π.support import archive_old_documents, cleanup_old_logs, get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import StagedWorkflow

logger = logging.getLogger(__name__)
VERSION = get_version("pi-rpi")


def _create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="π",
        description="Autonomous Research → Plan → Review → Implement workflow.",
    )
    parser.add_argument("objective", nargs="?", help="The objective for the agent")
    return parser


# Load environment variables
load_dotenv()


def run_workflow_mode(objective: str) -> None:
    """Execute objective using StagedWorkflow pipeline."""
    print(f"[Workflow Mode] Using {Provider.Claude} with staged pipeline")
    print(">  Stages: Research → Design → Execute")

    lm = get_lm(Provider.Claude, Tier.HIGH)
    workflow = StagedWorkflow(lm=lm)

    result = workflow(objective=objective)

    print("\n=== Workflow Complete ===")
    print(f"Status: {result.status}")

    if hasattr(result, "reason") and result.reason:
        print(f"Reason: {result.reason}")
    if hasattr(result, "research_doc_path"):
        print(f"Research Doc: {result.research_doc_path}")
    if hasattr(result, "plan_doc_path"):
        print(f"Plan Doc: {result.plan_doc_path}")
    if hasattr(result, "files_changed") and result.files_changed:
        print(f"Files Changed: {result.files_changed}")
    if hasattr(result, "commit_hash") and result.commit_hash:
        print(f"Commit: {result.commit_hash}")


@prevent_sleep
def main(argv: list[str] | None = None) -> None:
    """Run the π agent with the given OBJECTIVE."""
    parser = _create_parser()
    args = parser.parse_args(argv)

    logger.info(f"π (v{VERSION})")
    print(f"π (v{VERSION})")

    # Use positional arg if provided, otherwise try stdin if piped
    if args.objective:
        objective = args.objective
    elif not sys.stdin.isatty():
        try:
            objective = sys.stdin.read().strip()
        except OSError:
            objective = None
    else:
        objective = None

    if not objective:
        parser.print_help()
        return

    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)  # Clean old logs first
    archive_old_documents()  # Archive old research/plan documents
    log_path = setup_logging(logs_dir)

    logger.info("Objective: %s", objective)

    print(f"Logging to: {log_path}")

    run_workflow_mode(objective)

    speak("π complete")

    # Only show log path if file was actually created
    logging.shutdown()  # Ensure all handlers flushed/closed
    if log_path.exists():
        print(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
