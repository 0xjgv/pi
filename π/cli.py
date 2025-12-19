import click
import dspy
from dotenv import load_dotenv

from π.config import THINKING_MODELS, configure_dspy
from π.utils import setup_logging
from π.workflow import (
    clarify_goal,
    create_plan,
    implement_plan,
    logger,
    research_codebase,
)

# Load environment variables
load_dotenv()


class AgentTask(dspy.Signature):
    """Answer the objective using the available tools."""

    objective: str = dspy.InputField()
    output: str = dspy.OutputField()


@click.command()
@click.argument("objective")
@click.option(
    "--thinking",
    "-t",
    type=click.Choice(["low", "med", "high"]),
    default="low",
    help="Thinking level: low=haiku (default), med=sonnet, high=opus",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable debug logging",
)
def main(objective: str, thinking: str, verbose: bool) -> None:
    """Run the ReAct agent with the given OBJECTIVE."""
    configure_dspy(model=THINKING_MODELS[thinking], logger=logger)
    setup_logging(verbose)

    click.echo(f"Starting ReAct Agent [{thinking}] with: '{objective}'")

    agent = dspy.ReAct(
        tools=[
            research_codebase,
            implement_plan,
            clarify_goal,
            create_plan,
        ],
        signature=AgentTask,
    )
    result = agent(objective=objective)

    click.echo(f"\nFinal Answer: {result.output}")


if __name__ == "__main__":
    main()
