import logging
from importlib.metadata import version

import click
from dotenv import load_dotenv

from π.config import Provider
from π.support import cleanup_old_logs, get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import (
    RPIWorkflow,
)

logger = logging.getLogger(__name__)  # Use module's own logger

# Load environment variables
load_dotenv()


def run_workflow_mode(objective: str) -> None:
    """Execute objective using RPIWorkflow pipeline."""
    click.echo(f"[Workflow Mode] Using {Provider.Claude} with per-stage models")
    click.echo(">  Stages: Research(high) → Plan(high) → Review(high)")

    workflow = RPIWorkflow()
    result = workflow(objective=objective)

    click.echo("\n=== Workflow Complete ===")
    click.echo(f"Research Doc: {result.research_doc_path}")
    click.echo(f"Plan Doc: {result.plan_doc_path}")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version("pi-rpi"), "-v", "--version", prog_name="π")
@click.argument("objective", required=False)
@click.pass_context
@prevent_sleep
def main(
    ctx: click.Context,
    objective: str | None,
) -> None:
    """Run the π agent with the given OBJECTIVE."""
    if not objective:
        click.echo(ctx.get_help())
        ctx.exit(0)

    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)  # Clean old logs first
    log_path = setup_logging(logs_dir)

    click.echo(f"Logging to: {log_path}")

    run_workflow_mode(objective)

    speak("π complete")

    if log_path:
        click.echo(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
