"""CLI entry point for π workflow using Claude Agent SDK with MCP tools.

Demonstrates how to use custom MCP tools (research, plan, implement, etc.)
with the Claude SDK client. Structured output ensures the orchestrator must
call tools to fill required fields (can't hallucinate file paths, etc.).
"""

import argparse
import asyncio
import logging
import sys
from importlib.metadata import version as get_version

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage
from dotenv import load_dotenv

from π.cli.display import LiveObserver
from π.config import get_logs_dir, get_orchestrator_options, setup_logging
from π.console import console
from π.support.directory import get_project_root
from π.utils import prevent_sleep, speak
from π.workflow import (
    CompositeObserver,
    LoggingObserver,
    WorkflowOutput,
    dispatch_message,
    get_workflow_ctx,
    reset_workflow_ctx,
)
from π.workflow.tools import WORKFLOW_TOOLS, workflow_server

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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging to console",
    )
    return parser


async def run(objective: str, *, verbose: bool = False) -> WorkflowOutput | None:
    """Run the Claude agent with workflow MCP tools.

    The orchestrator uses structured output to ensure it must call tools
    to satisfy required fields. Tools provide ground truth for file paths,
    commit hashes, and other verifiable data.

    Args:
        objective: The workflow objective/goal to execute.
        verbose: If True, enable debug logging to console.

    Returns:
        WorkflowOutput if structured output was received, None otherwise.
    """
    # Set up logging infrastructure
    logs_dir = get_logs_dir()
    log_path = setup_logging(logs_dir, verbose=verbose)

    # Initialize fresh context with objective
    reset_workflow_ctx()
    ctx = get_workflow_ctx()
    ctx.objective = objective

    # Get orchestrator options and extend with MCP workflow tools
    options = get_orchestrator_options(cwd=get_project_root())
    options.mcp_servers = {"workflow": workflow_server}
    options.allowed_tools += WORKFLOW_TOOLS

    # Enable structured output - forces schema compliance
    # The orchestrator MUST call tools to fill required fields
    options.output_format = {
        "type": "json_schema",
        "schema": WorkflowOutput.model_json_schema(),
    }

    # Create observers: Live display + File logging
    system_prompt = str(options.system_prompt) if options.system_prompt else None
    log_observer = LoggingObserver(
        log_path,
        system_prompt=system_prompt,
        objective=objective,
    )
    live_observer = LiveObserver()
    observer = CompositeObserver([live_observer, log_observer])

    # Store observer in context for stage agents to use
    ctx.observer = observer

    workflow_result: WorkflowOutput | None = None

    async with ClaudeSDKClient(options=options) as client:
        await client.query(objective)
        with live_observer:  # Only LiveObserver needs context manager for Rich
            async for message in client.receive_response():
                dispatch_message(message, observer)

                # Capture structured output from ResultMessage
                if isinstance(message, ResultMessage) and message.structured_output:
                    try:
                        workflow_result = WorkflowOutput.model_validate(
                            message.structured_output
                        )
                        logger.info(
                            "Structured output received: status=%s, commit=%s",
                            workflow_result.status,
                            workflow_result.commit_hash,
                        )
                    except Exception as e:
                        logger.warning("Failed to validate structured output: %s", e)

    # Log final context state
    ctx = get_workflow_ctx()
    if ctx.session_ids or ctx.doc_paths:
        live_observer.console.print("\n[dim]Session IDs:[/dim]", ctx.session_ids)
        live_observer.console.print("[dim]Doc Paths:[/dim]", ctx.doc_paths)

    # Log structured output summary
    if workflow_result:
        live_observer.console.print("\n[bold]Workflow Output:[/bold]")
        live_observer.console.print(f"  Status: {workflow_result.status}")
        live_observer.console.print(f"  Research: {workflow_result.research_doc_path}")
        if workflow_result.plan_doc_path:
            live_observer.console.print(f"  Plan: {workflow_result.plan_doc_path}")
        if workflow_result.commit_hash:
            live_observer.console.print(f"  Commit: {workflow_result.commit_hash}")
        live_observer.console.print(f"  Summary: {workflow_result.summary}")

    # Show log path
    logging.shutdown()  # Ensure all handlers flushed
    if log_path.exists():
        live_observer.console.print(f"\n[dim]Debug log:[/dim] {log_path}")

    return workflow_result


@prevent_sleep
def main(argv: list[str] | None = None) -> None:
    """Run the π agent with the given OBJECTIVE."""
    load_dotenv()
    parser = _create_parser()
    args = parser.parse_args(argv)

    logger.info(f"π (v{VERSION})")
    console.print(f"[heading]π[/heading] [muted](v{VERSION})[/muted]")

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

    asyncio.run(run(objective, verbose=args.verbose))
    speak("workflow complete")


if __name__ == "__main__":
    main()
