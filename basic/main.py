"""Basic example using Claude Agent SDK with MCP workflow tools.

Demonstrates how to use custom MCP tools (research, plan, implement, etc.)
with the Claude SDK client. Structured output ensures the orchestrator must
call tools to fill required fields (can't hallucinate file paths, etc.).
"""

import asyncio
import logging

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage

from basic.config import get_logs_dir, get_orchestrator_options, setup_logging
from basic.context import get_workflow_ctx, reset_workflow_ctx
from basic.display import LiveObserver
from basic.models import WorkflowOutput
from basic.observer import CompositeObserver, LoggingObserver, dispatch_message
from basic.tools import WORKFLOW_TOOLS, workflow_server
from π.support.directory import get_project_root
from π.utils import prevent_sleep, speak

logger = logging.getLogger(__name__)


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
def main(objective: str | None = None, *, verbose: bool = False) -> None:
    """Sync entry point with sleep prevention.

    Wraps the async run() function with caffeinate to prevent macOS
    from sleeping during long-running workflows.

    Args:
        objective: The workflow objective. If None, uses default.
        verbose: Enable debug logging to console.
    """
    if objective is None:
        objective = "Research the authentication flow in the codebase, create a plan."

    asyncio.run(run(objective, verbose=verbose))
    speak("workflow complete")


if __name__ == "__main__":
    main(
        "How would you move this basic directory to the root of the project "
        "while removing everything else that is not needed? "
        "Our goal is to replace the CLI with our basic main approach"
    )
