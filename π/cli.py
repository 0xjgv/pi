from importlib.metadata import version

import click
import dspy
from dotenv import load_dotenv

from π.config import Provider, get_lm, get_model
from π.directory import get_logs_dir
from π.router import ExecutionMode, classify_objective
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import (
    clarify_goal,
    create_plan,
    logger,
    research_codebase,
)
from π.workflow_module import RPIWorkflow

# Load environment variables
load_dotenv()


class AgentTask(dspy.Signature):
    """Answer the objective using the available tools."""

    objective: str = dspy.InputField()
    output: str = dspy.OutputField()


def run_simple_mode(
    objective: str,
    provider: Provider,
    tier: str,
    log_path: str,
) -> None:
    """Execute objective using simple ReAct agent."""
    model = get_model(provider=provider, tier=tier)
    lm = get_lm(provider=provider, tier=tier)

    click.echo(f"[Simple Mode] Using {provider}/{tier}")
    click.echo(f"Model: {model}")

    agent = dspy.ReAct(
        # tools=[research_codebase, clarify_goal, create_plan, implement_plan],
        tools=[research_codebase, clarify_goal, create_plan],
        signature=AgentTask,
    )

    with dspy.context(lm=lm):
        result = agent(objective=objective)

    click.echo(f"\nFinal Answer: {result.output}")


def run_workflow_mode(objective: str, provider: Provider, log_path: str) -> None:
    """Execute objective using RPIWorkflow pipeline."""
    click.echo(f"[Workflow Mode] Using {provider} with per-stage models")
    click.echo("  Stages: Clarify(low) → Research(high) → Plan(high) → Implement(med)")

    workflow = RPIWorkflow(provider=provider)
    result = workflow(objective=objective)

    click.echo("\n=== Workflow Complete ===")
    click.echo(f"Clarified Objective: {result.clarified_objective}")
    click.echo(f"Research Doc: {result.research_doc_path}")
    click.echo(f"Plan Doc: {result.plan_doc_path}")
    click.echo(f"\nImplementation Summary:\n{result.implementation_summary}")


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=version("pi-rpi"), prog_name="π")
@click.argument("objective")
@click.option(
    "--thinking",
    "-t",
    help="Thinking level: low=haiku (default), med=sonnet, high=opus",
    type=click.Choice(["low", "med", "high"], case_sensitive=False),
    default="low",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice([p.value for p in Provider], case_sensitive=False),
    help="AI provider: claude (default), antigravity, openai",
    default=Provider.Claude.value,
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["auto", "simple", "workflow"], case_sensitive=False),
    help="Execution mode: auto uses router, or force simple/workflow",
    default="auto",
)
@prevent_sleep
def main(objective: str, thinking: str, provider: str, mode: str) -> None:
    """Run the π agent with the given OBJECTIVE."""
    provider_enum = Provider(provider.lower())
    log_path = setup_logging(get_logs_dir())

    click.echo(f"Objective: '{objective}'")
    click.echo(f"Logging to: {log_path}")

    # Determine execution mode
    if mode == "auto":
        click.echo("Classifying objective...")
        exec_mode = classify_objective(
            objective,
            provider=provider_enum,
            logger=logger,
        )
        click.echo(f"Router selected: {exec_mode.value}")
    else:
        exec_mode = ExecutionMode(mode)
        click.echo(f"Forced mode: {exec_mode.value}")

    # Execute based on mode
    if exec_mode == ExecutionMode.SIMPLE:
        run_simple_mode(objective, provider_enum, thinking.lower(), log_path)
    else:
        run_workflow_mode(objective, provider_enum, log_path)

    speak("π complete")

    if log_path:
        click.echo(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
