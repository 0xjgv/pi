"""CLI entry point for the π workflow agent."""

import argparse
import logging
import sys
from importlib.metadata import version as get_version

from dotenv import load_dotenv
from rich.panel import Panel
from rich.prompt import Confirm

from π.cli.live_display import LiveArtifactDisplay
from π.console import console
from π.core import Provider, Tier, get_lm
from π.support import archive_old_documents, cleanup_old_logs, get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import CheckpointManager, CheckpointState, StagedWorkflow

logger = logging.getLogger(__name__)
VERSION = get_version("pi-rpi")


def _create_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="π",
        description="Autonomous Research → Plan → Review → Implement workflow.",
    )
    parser.add_argument("objective", nargs="?", help="The objective for the agent")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per stage (default: 3)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore existing checkpoint and start fresh",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Delete existing checkpoint and exit (does not run workflow)",
    )
    return parser


# Load environment variables
load_dotenv()


def _check_resume(
    checkpoint: CheckpointManager,
    objective: str,
) -> CheckpointState | None:
    """Check for existing checkpoint and prompt for resume."""

    state = checkpoint.load()
    if not state:
        return None

    # Different objective - clear and start fresh
    if state.objective != objective:
        console.print(
            "[yellow]Checkpoint exists for different objective, ignoring[/yellow]"
        )
        checkpoint.clear()
        return None

    resume_stage = checkpoint.get_resume_stage()
    if not resume_stage:
        return None

    # Prompt user for resume
    last_stage = state.last_completed_stage
    prompt = (
        f"[yellow]Found checkpoint at stage '{last_stage}'. "
        f"Resume from '{resume_stage}'?[/yellow]\n"
        "[dim](Note: Stage will restart from the beginning, not mid-execution)[/dim]"
    )
    if Confirm.ask(prompt, default=True):
        console.print(
            f"[muted]Resuming from stage:[/muted] [success]{resume_stage}[/success]"
        )
        return state

    checkpoint.clear()
    console.print("[muted]Starting fresh workflow[/muted]")
    return None


def run_workflow_mode(
    objective: str,
    *,
    max_retries: int = 3,
    no_resume: bool = False,
) -> None:
    """Execute objective using StagedWorkflow pipeline."""
    checkpoint = CheckpointManager(max_retries=max_retries)
    resume_state = None

    # Check for existing checkpoint
    if not no_resume and checkpoint.has_checkpoint():
        resume_state = _check_resume(checkpoint, objective)

    lm = get_lm(Provider.Claude, Tier.HIGH)
    workflow = StagedWorkflow(lm=lm, checkpoint=checkpoint)

    display = LiveArtifactDisplay()
    display.start()
    try:
        result = workflow(objective=objective, resume_state=resume_state)
    finally:
        display.stop()

    # Build summary content
    lines = [f"[success]Status:[/success] {result.status}"]
    if reason := getattr(result, "reason", None):
        lines.append(f"[muted]Reason:[/muted] {reason}")
    if research := getattr(result, "research_doc_path", None):
        lines.append(f"[muted]Research:[/muted] [path]{research}[/]")
    if plan := getattr(result, "plan_doc_path", None):
        lines.append(f"[muted]Plan:[/muted] [path]{plan}[/]")
    if files := getattr(result, "files_changed", None):
        lines.append(f"[muted]Files:[/muted] {files}")
    if commit := getattr(result, "commit_hash", None):
        lines.append(f"[muted]Commit:[/muted] [path]{commit}[/]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[success]Workflow Complete[/success]",
            border_style="green",
        )
    )


@prevent_sleep
def main(argv: list[str] | None = None) -> None:
    """Run the π agent with the given OBJECTIVE."""
    parser = _create_parser()
    args = parser.parse_args(argv)

    logger.info(f"π (v{VERSION})")
    console.print(f"[heading]π[/heading] [muted](v{VERSION})[/muted]")

    # Handle --clear-checkpoint before anything else
    if args.clear_checkpoint:
        checkpoint = CheckpointManager()
        if checkpoint.has_checkpoint():
            checkpoint.clear()
            console.print("[success]Checkpoint cleared[/success]")
        else:
            console.print("[muted]No checkpoint to clear[/muted]")
        return

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

    console.print(f"[muted]Logging to:[/muted] [path]{log_path}[/path]")

    run_workflow_mode(
        objective,
        max_retries=args.max_retries,
        no_resume=args.no_resume,
    )

    speak("π complete")

    # Only show log path if file was actually created
    logging.shutdown()  # Ensure all handlers flushed/closed
    if log_path.exists():
        console.print(f"\n[muted]Debug log:[/muted] [path]{log_path}[/path]")


if __name__ == "__main__":
    main()
