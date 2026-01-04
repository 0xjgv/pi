import argparse
import logging
import sys
from importlib.metadata import version as get_version

from dotenv import load_dotenv

from π.config import STAGE_TIERS, Provider, Tier, get_lm
from π.support import cleanup_old_logs, get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import (
    RPIWorkflow,
)
from π.workflow.loop import LoopStatus, ObjectiveLoop, TaskStatus

logger = logging.getLogger(__name__)  # Use module's own logger
VERSION = get_version("pi-rpi")


def _create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="π",
        description="Autonomous Research → Plan → Review → Implement workflow.",
    )
    parser.add_argument("objective", nargs="?", help="The objective for the agent")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Use iterative loop mode for complex objectives",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, ignore existing loop state",
    )
    return parser


# Load environment variables
load_dotenv()


def _format_stages() -> str:
    """Format STAGE_TIERS as 'Name(tier) → Name(tier) → ...'"""
    parts = [
        f"{stage.value.replace('_', ' ').title()} ({tier})"
        for stage, tier in STAGE_TIERS.items()
    ]
    return " → ".join(parts)


def run_workflow_mode(objective: str) -> None:
    """Execute objective using RPIWorkflow pipeline."""
    print(f"[Workflow Mode] Using {Provider.Claude} with per-stage models")
    print(f">  Stages: {_format_stages()}")

    # Default LM
    lm = get_lm(Provider.Claude, Tier.HIGH)

    workflow = RPIWorkflow(lm=lm)
    result = workflow(objective=objective)

    print("\n=== Workflow Complete ===")
    print(f"Research Doc: {result.research_doc_path}")
    print(f"Plan Doc: {result.plan_doc_path}")
    print(f"Implementation: {result.implementation_status}")
    print(f"Files Changed: {result.files_changed}")
    print(f"Commit: {result.commit_result}")


def run_loop_mode(objective: str, *, resume: bool = True) -> None:
    """Execute objective using iterative ObjectiveLoop."""
    print("[Loop Mode] Iterating toward objective")
    print(">  Max iterations: 50")
    print(f">  Resume: {resume}")

    lm = get_lm(Provider.Claude, Tier.HIGH)
    loop = ObjectiveLoop(lm=lm)

    state = loop(objective=objective, resume=resume)

    print("\n=== Loop Complete ===")
    print(f"Status: {state.status}")
    print(f"Iterations: {state.iteration}")
    print(f"Completed Tasks: {len(state.completed_task_ids)}/{len(state.tasks)}")

    if state.status == LoopStatus.COMPLETED:
        print("\nCompleted tasks:")
        for task in state.tasks:
            if task.status == TaskStatus.COMPLETED:
                print(f"  - {task.description}")


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
    log_path = setup_logging(logs_dir)

    print(f"Logging to: {log_path}")

    if args.loop:
        run_loop_mode(objective, resume=not args.no_resume)
    else:
        run_workflow_mode(objective)

    speak("π complete")

    # Only show log path if file was actually created
    logging.shutdown()  # Ensure all handlers flushed/closed
    if log_path.exists():
        print(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
