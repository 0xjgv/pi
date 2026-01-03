import argparse
import json
import logging
import sys
from importlib.metadata import version as get_version
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from π.config import STAGE_TIERS, Provider, Tier, get_lm
from π.orchestrator import (
    OrchestratorAgent,
    OrchestratorStatus,
    get_latest_state,
    list_states,
    load_state_by_hash,
)
from π.orchestrator.tools import format_status_display
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
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Read objective from file (e.g., prompt.md)",
    )
    parser.add_argument(
        "--resume",
        "-r",
        nargs="?",
        const=True,
        metavar="HASH",
        help="Resume existing objective (auto-detect or specify hash)",
    )
    parser.add_argument(
        "--orchestrator",
        "-o",
        action="store_true",
        help="Use orchestrator mode with persistent state",
    )
    parser.add_argument(
        "--status",
        "-s",
        action="store_true",
        help="Show orchestrator status",
    )
    parser.add_argument(
        "--status-json",
        action="store_true",
        help="Output status as JSON",
    )
    parser.add_argument(
        "--status-all",
        action="store_true",
        help="Show all saved states",
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


def run_orchestrator_mode(objective: str) -> None:
    """Execute objective using OrchestratorAgent with persistent state."""
    console = Console()
    console.print(f"[bold cyan][Orchestrator Mode][/bold cyan] Using {Provider.Claude}")
    console.print(f">  Objective: {objective[:100]}...")

    agent = OrchestratorAgent()
    result = agent.forward(objective=objective)

    console.print("\n[bold]=== Orchestrator Complete ===[/bold]")
    console.print(f"Status: {result.status}")
    console.print(f"Tasks: {result.tasks_completed}/{result.tasks_total} completed")
    console.print(f"Iterations: {result.iterations}")

    if result.halt_reason:
        console.print(f"[red]Halted:[/red] {result.halt_reason}")


def resume_orchestrator(obj_hash: str | None = None) -> None:
    """Resume orchestrator from saved state.

    Args:
        obj_hash: Specific hash to resume, or None to auto-detect latest.
    """
    console = Console()

    if obj_hash and obj_hash is not True:
        # Resume specific hash
        state = load_state_by_hash(obj_hash)
        if not state:
            console.print(f"[red]Error:[/red] No state found for hash: {obj_hash}")
            return
    else:
        # Auto-detect latest
        state = get_latest_state()
        if not state:
            console.print("[yellow]No saved states found.[/yellow]")
            console.print("Start a new objective with: π --orchestrator 'your objective'")
            return

    console.print(f"[bold cyan][Resuming][/bold cyan] {state.objective[:80]}...")
    console.print(f">  Hash: {state.objective_hash}")
    console.print(f">  Status: {state.status.value}")

    if state.status == OrchestratorStatus.COMPLETED:
        console.print("[green]This objective is already complete.[/green]")
        return

    agent = OrchestratorAgent()
    result = agent.resume(state.objective_hash)

    console.print("\n[bold]=== Orchestrator Complete ===[/bold]")
    console.print(f"Status: {result.status}")
    console.print(f"Tasks: {result.tasks_completed}/{result.tasks_total} completed")


def status_command(*, as_json: bool = False, show_all: bool = False) -> None:
    """Display orchestrator status.

    Args:
        as_json: Output as JSON instead of formatted text.
        show_all: Show all saved states, not just latest.
    """
    console = Console()

    if show_all:
        states = list_states()
        if not states:
            if as_json:
                print(json.dumps([]))
            else:
                console.print("[yellow]No saved states found.[/yellow]")
            return

        if as_json:
            output = [s.to_dict() for s in states]
            print(json.dumps(output, indent=2))
        else:
            console.print(f"[bold]Saved States ({len(states)}):[/bold]\n")
            for state in states:
                status_color = {
                    OrchestratorStatus.RUNNING: "yellow",
                    OrchestratorStatus.COMPLETED: "green",
                    OrchestratorStatus.HALTED: "red",
                }.get(state.status, "white")

                completed = sum(1 for t in state.tasks if t.status.value == "completed")
                total = len(state.tasks)

                console.print(
                    f"[{status_color}]{state.status.value:9}[/{status_color}] "
                    f"[dim]{state.objective_hash}[/dim] "
                    f"({completed}/{total} tasks) "
                    f"{state.objective[:50]}..."
                )
    else:
        state = get_latest_state()
        if not state:
            if as_json:
                print(json.dumps(None))
            else:
                console.print("[yellow]No saved states found.[/yellow]")
                console.print("Start a new objective with: π --orchestrator 'your objective'")
            return

        if as_json:
            print(json.dumps(state.to_dict(), indent=2))
        else:
            console.print(format_status_display(state))


@prevent_sleep
def main(argv: list[str] | None = None) -> None:
    """Run the π agent with the given OBJECTIVE."""
    parser = _create_parser()
    args = parser.parse_args(argv)

    logger.info(f"π (v{VERSION})")
    print(f"π (v{VERSION})")

    # Handle status command
    if args.status or args.status_json or args.status_all:
        status_command(as_json=args.status_json, show_all=args.status_all)
        return

    # Handle resume mode
    if args.resume:
        logs_dir = get_logs_dir()
        cleanup_old_logs(logs_dir)
        log_path = setup_logging(logs_dir)
        print(f"Logging to: {log_path}")

        # args.resume is True for --resume, or a string hash for --resume HASH
        obj_hash = args.resume if isinstance(args.resume, str) else None
        resume_orchestrator(obj_hash)

        speak("π complete")
        logging.shutdown()
        if log_path.exists():
            print(f"\nDebug log: {log_path}")
        return

    # Determine objective from various sources
    objective: str | None = None

    # 1. From --file argument
    if args.file:
        if args.file.exists():
            objective = args.file.read_text().strip()
        else:
            print(f"Error: File not found: {args.file}")
            return

    # 2. From positional argument
    elif args.objective:
        objective = args.objective

    # 3. From stdin if piped
    elif not sys.stdin.isatty():
        try:
            objective = sys.stdin.read().strip()
        except OSError:
            objective = None

    if not objective:
        parser.print_help()
        return

    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)  # Clean old logs first
    log_path = setup_logging(logs_dir)

    print(f"Logging to: {log_path}")

    # Choose execution mode
    if args.orchestrator:
        run_orchestrator_mode(objective)
    else:
        run_workflow_mode(objective)

    speak("π complete")

    # Only show log path if file was actually created
    logging.shutdown()  # Ensure all handlers flushed/closed
    if log_path.exists():
        print(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
