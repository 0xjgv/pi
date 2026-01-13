#!/usr/bin/env python3
"""Workflow orchestrator - autonomous research -> design -> execute pipeline.

Consolidates isolated SDK sessions with structured JSON output and logging.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock
from pydantic import BaseModel

# =============================================================================
# MODELS
# =============================================================================


class Status(str, Enum):
    """Workflow result status."""

    SUCCESS = "success"
    ERROR = "error"
    EARLY_EXIT = "early_exit"


class Stage(str, Enum):
    """Workflow stage identifier."""

    RESEARCH = "research"
    DESIGN = "design"
    EXECUTE = "execute"


class WorkflowResult(BaseModel):
    """Structured output for workflow stages."""

    status: Status
    stage: Stage
    output_path: str | None = None
    implementation_needed: bool | None = None
    summary: str
    error: str | None = None


# =============================================================================
# LOGGING (copied from pi for portability)
# =============================================================================

DEFAULT_LOG_RETENTION_DAYS = 7
logger = logging.getLogger("workflow")


def get_logs_dir(root: Path | None = None) -> Path:
    """Get logs directory, creating .pi/logs/ if needed."""
    root = root or Path.cwd()
    logs_dir = root / ".π" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def cleanup_old_logs(
    logs_dir: Path, retention_days: int = DEFAULT_LOG_RETENTION_DAYS
) -> int:
    """Remove log files older than retention_days."""
    if not logs_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = 0

    for log_file in logs_dir.glob("workflow-*.log"):
        try:
            # Parse date from filename: workflow-YYYY-MM-DD-HH:MM.log
            date_str = log_file.stem[9:19]  # Extract YYYY-MM-DD after "workflow-"
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue

    return deleted


def setup_logging(log_dir: Path, *, verbose: bool = False) -> Path:
    """Configure logging - same format as pi CLI."""
    logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M")
    log_path = log_dir / f"workflow-{timestamp}.log"

    file_handler = logging.FileHandler(log_path, delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    if verbose:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(console_handler)

    logger.setLevel(logging.DEBUG)

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return log_path


# =============================================================================
# SESSION
# =============================================================================


class ClaudeSession:
    """Run commands in isolated SDK sessions."""

    def __init__(self, *, working_dir: Path | None = None) -> None:
        self.working_dir = working_dir or Path.cwd()

    async def run_command(self, command: str, context: str = "") -> str:
        """Run a slash command and return the raw output."""
        prompt = f"{command}\n\n{context}" if context else command
        result_content = ""
        result_parts: list[str] = []

        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            cwd=self.working_dir,
            setting_sources=["project"],
        )

        logger.info("Running command: %s", command)
        logger.debug("Context: %s", context[:200] if context else "(none)")

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt, session_id="default")

            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    if message.result:
                        result_content = message.result
                    break
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_parts.append(block.text)

        result = result_content if result_content else "\n".join(result_parts)
        logger.info("Command completed: %d chars", len(result))
        return result


# =============================================================================
# STAGE RUNNERS
# =============================================================================


def _extract_path(output: str, directory: str) -> str | None:
    """Extract document path from SDK output."""
    pattern = rf"{re.escape(directory)}/\d{{4}}-\d{{2}}-\d{{2}}-[^\s\"')\]]+\.md"
    match = re.search(pattern, output)
    return match.group(0) if match else None


def _truncate(text: str, length: int = 500) -> str:
    """Truncate text with ellipsis."""
    return text[:length] + "..." if len(text) > length else text


async def run_research(session: ClaudeSession, objective: str) -> WorkflowResult:
    """Stage 1: Research codebase."""
    logger.info("=== Stage: Research ===")
    try:
        result = await session.run_command("/1_research_codebase", objective)
        output_path = _extract_path(result, "thoughts/shared/research")

        # Check for early exit signals
        result_lower = result.lower()
        impl_needed = not (
            "no implementation" in result_lower
            or "no changes" in result_lower
            or "nothing to implement" in result_lower
        )

        status = Status.SUCCESS if impl_needed else Status.EARLY_EXIT
        logger.info("Research complete: impl_needed=%s, path=%s", impl_needed, output_path)

        return WorkflowResult(
            status=status,
            stage=Stage.RESEARCH,
            output_path=output_path,
            implementation_needed=impl_needed,
            summary=_truncate(result),
        )
    except Exception as e:
        logger.exception("Research stage failed")
        return WorkflowResult(
            status=Status.ERROR,
            stage=Stage.RESEARCH,
            summary="Research failed",
            error=str(e),
        )


async def run_design(
    session: ClaudeSession, objective: str, research_doc: str | None
) -> WorkflowResult:
    """Stage 2: Create implementation plan."""
    logger.info("=== Stage: Design ===")
    try:
        context = f"Objective: {objective}"
        if research_doc:
            context += f"\n\nResearch document: {research_doc}"

        result = await session.run_command("/2_create_plan", context)
        output_path = _extract_path(result, "thoughts/shared/plans")
        logger.info("Design complete: path=%s", output_path)

        return WorkflowResult(
            status=Status.SUCCESS,
            stage=Stage.DESIGN,
            output_path=output_path,
            summary=_truncate(result),
        )
    except Exception as e:
        logger.exception("Design stage failed")
        return WorkflowResult(
            status=Status.ERROR,
            stage=Stage.DESIGN,
            summary="Design failed",
            error=str(e),
        )


async def run_execute(
    session: ClaudeSession, objective: str, plan_doc: str
) -> WorkflowResult:
    """Stage 3: Implement plan."""
    logger.info("=== Stage: Execute ===")
    try:
        context = f"Objective: {objective}\n\nPlan document: {plan_doc}"
        result = await session.run_command("/5_implement_plan", context)
        logger.info("Execute complete")

        return WorkflowResult(
            status=Status.SUCCESS,
            stage=Stage.EXECUTE,
            output_path=plan_doc,
            summary=_truncate(result),
        )
    except Exception as e:
        logger.exception("Execute stage failed")
        return WorkflowResult(
            status=Status.ERROR,
            stage=Stage.EXECUTE,
            summary="Execute failed",
            error=str(e),
        )


async def run_all(
    objective: str,
    *,
    research_doc: str | None = None,
    plan_doc: str | None = None,
) -> WorkflowResult:
    """Run all stages sequentially with early exit."""
    session = ClaudeSession()
    logger.info("Starting full workflow: %s", objective)

    # Stage 1: Research (unless research_doc provided)
    if not research_doc:
        result = await run_research(session, objective)
        if result.status == Status.ERROR:
            return result
        if not result.implementation_needed:
            logger.info("Early exit: no implementation needed")
            return result
        research_doc = result.output_path

    # Stage 2: Design (unless plan_doc provided)
    if not plan_doc:
        result = await run_design(session, objective, research_doc)
        if result.status == Status.ERROR:
            return result
        plan_doc = result.output_path

    # Stage 3: Execute
    if not plan_doc:
        return WorkflowResult(
            status=Status.ERROR,
            stage=Stage.EXECUTE,
            summary="No plan document available",
            error="Design stage did not produce a plan document",
        )

    return await run_execute(session, objective, plan_doc)


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="workflow",
        description="Autonomous research -> design -> execute workflow",
    )
    parser.add_argument("objective", help="The development objective")
    parser.add_argument(
        "--stage",
        choices=["research", "design", "execute", "all"],
        default="all",
        help="Stage to run (default: all)",
    )
    parser.add_argument("--research-doc", help="Path to existing research document")
    parser.add_argument("--plan-doc", help="Path to existing plan document")
    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of prose"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser


def print_human_readable(result: WorkflowResult) -> None:
    """Print result in human-readable format."""
    print(f"\n{'=' * 40}")
    print(f"Status: {result.status.value}")
    print(f"Stage: {result.stage.value}")
    if result.output_path:
        print(f"Output: {result.output_path}")
    if result.implementation_needed is not None:
        print(f"Implementation needed: {result.implementation_needed}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"{'=' * 40}")
    print(f"\n{result.summary}")


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)
    log_path = setup_logging(logs_dir, verbose=args.verbose)
    logger.info("Workflow started: %s (log: %s)", args.objective, log_path)

    # Dispatch to appropriate stage
    session = ClaudeSession()

    if args.stage == "research":
        result = asyncio.run(run_research(session, args.objective))
    elif args.stage == "design":
        if not args.research_doc:
            parser.error("--research-doc required for design stage")
        result = asyncio.run(run_design(session, args.objective, args.research_doc))
    elif args.stage == "execute":
        if not args.plan_doc:
            parser.error("--plan-doc required for execute stage")
        result = asyncio.run(run_execute(session, args.objective, args.plan_doc))
    else:  # all
        result = asyncio.run(
            run_all(
                args.objective,
                research_doc=args.research_doc,
                plan_doc=args.plan_doc,
            )
        )

    # Output
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print_human_readable(result)

    # Exit code
    exit_codes = {Status.SUCCESS: 0, Status.ERROR: 1, Status.EARLY_EXIT: 2}
    sys.exit(exit_codes[result.status])


if __name__ == "__main__":
    main()
