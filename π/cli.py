import click
import dspy
from dotenv import load_dotenv

from π.config import Provider, configure_dspy, get_model
from π.directory import get_logs_dir
from π.utils import prevent_sleep, setup_logging, speak
from π.workflow import (
    clarify_goal,
    create_plan,
    logger,
    research_codebase,
)

# Load environment variables
load_dotenv()


class AgentTask(dspy.Signature):
    """Answer the objective using the available tools."""

    objective: str = dspy.InputField()
    output: str = dspy.OutputField()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
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
@prevent_sleep
def main(objective: str, thinking: str, provider: str) -> None:
    """Run the ReAct agent with the given OBJECTIVE."""
    provider_enum = Provider(provider.lower())
    model = get_model(provider=provider_enum, tier=thinking.lower())

    configure_dspy(model=model, logger=logger)
    log_path = setup_logging(get_logs_dir())

    click.echo(f"Starting ReAct Agent [{provider}/{thinking}] with: '{objective}'")
    click.echo(f"Logging to: {log_path}")
    click.echo(f"Using model: {model}")

    # Create and execute the agent
    agent = dspy.ReAct(
        tools=[research_codebase, clarify_goal, create_plan],
        signature=AgentTask,
    )
    result = agent(objective=objective)

    click.echo(f"\nFinal Answer: {result.output}")
    speak("π complete")

    if log_path:
        click.echo(f"\nDebug log: {log_path}")


if __name__ == "__main__":
    main()
