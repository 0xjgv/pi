import argparse
import logging
from importlib.metadata import version as get_version

from dotenv import load_dotenv

from π.config import STAGE_TIERS, Provider
from π.support import cleanup_old_logs, get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import (
    RPIWorkflow,
)

logger = logging.getLogger(__name__)  # Use module's own logger
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

    workflow = RPIWorkflow()
    result = workflow(objective=objective)

    print("\n=== Workflow Complete ===")
    print(f"Research Doc: {result.research_doc_path}")
    print(f"Plan Doc: {result.plan_doc_path}")


@prevent_sleep
def main(argv: list[str] | None = None) -> None:
    """Run the π agent with the given OBJECTIVE."""
    parser = _create_parser()
    args = parser.parse_args(argv)

    logger.info(f"π (v{VERSION})")
    print(f"π (v{VERSION})")

    if not args.objective:
        parser.print_help()
        return

    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)  # Clean old logs first
    log_path = setup_logging(logs_dir)

    print(f"Logging to: {log_path}")

    run_workflow_mode(args.objective)

    speak("π complete")

    if log_path:
        print(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
