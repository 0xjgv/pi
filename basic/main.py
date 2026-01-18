"""Basic example using Claude Agent SDK with MCP workflow tools.

Demonstrates how to use custom MCP tools (research, plan, implement, etc.)
with the Claude SDK client. Context is shared across tool calls for session
management and document tracking.
"""

import asyncio
import logging

from claude_agent_sdk import ClaudeSDKClient

from basic.config import get_logs_dir, get_orchestrator_options, setup_logging
from basic.context import get_workflow_ctx, reset_workflow_ctx
from basic.display import LiveObserver
from basic.observer import CompositeObserver, LoggingObserver, dispatch_message
from basic.tools import WORKFLOW_TOOLS, workflow_server
from π.support.directory import get_project_root
from π.utils import prevent_sleep, speak


async def run(objective: str, *, verbose: bool = False) -> None:
    """Run the Claude agent with workflow MCP tools.

    Args:
        objective: The workflow objective/goal to execute.
        verbose: If True, enable debug logging to console.
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

    # Create observers: Live display + File logging
    system_prompt = str(options.system_prompt) if options.system_prompt else None
    log_observer = LoggingObserver(
        log_path,
        system_prompt=system_prompt,
        objective=objective,
    )
    live_observer = LiveObserver()
    observer = CompositeObserver([live_observer, log_observer])

    async with ClaudeSDKClient(options=options) as client:
        await client.query(objective)
        with live_observer:  # Only LiveObserver needs context manager for Rich
            async for message in client.receive_response():
                dispatch_message(message, observer)

    # Log final context state
    ctx = get_workflow_ctx()
    if ctx.session_ids or ctx.doc_paths:
        live_observer.console.print("\n[dim]Session IDs:[/dim]", ctx.session_ids)
        live_observer.console.print("[dim]Doc Paths:[/dim]", ctx.doc_paths)

    # Show log path
    logging.shutdown()  # Ensure all handlers flushed
    if log_path.exists():
        live_observer.console.print(f"\n[dim]Debug log:[/dim] {log_path}")


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
        "How would you move this basic directory to the root of the (π)project while removing everything else that is not needed? Our goal is to replace the π CLI with our basic main approach"
    )
