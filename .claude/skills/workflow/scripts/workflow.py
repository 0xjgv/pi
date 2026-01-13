#!/usr/bin/env python3
"""Workflow orchestrator - runs stages in isolated SDK sessions.

Each stage runs a slash command and prints the raw output.
The main agent reads output, finds paths, and makes decisions.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock

# =============================================================================
# LOGGING
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
            date_str = log_file.stem[9:19]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue

    return deleted


def setup_logging(log_dir: Path, *, verbose: bool = False) -> Path:
    """Configure logging."""
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
        prompt = f"{command} {context}" if context else command
        result_parts: list[str] = []
        result_content = ""

        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            cwd=self.working_dir,
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
# STAGES
# =============================================================================

STAGE_COMMANDS: dict[str, str] = {
    "research": "/1_research_codebase",
    "create_plan": "/2_create_plan",
    "review_plan": "/3_review_plan",
    "iterate_plan": "/4_iterate_plan",
    "implement": "/5_implement_plan",
    "commit": "/6_commit",
}


async def run_stage(session: ClaudeSession, stage: str, context: str) -> str:
    """Run a single stage command."""
    command = STAGE_COMMANDS[stage]
    logger.info("=== Stage: %s (%s) ===", stage, command)
    return await session.run_command(command, context)


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog="workflow",
        description="Run workflow stages in isolated SDK sessions",
    )
    parser.add_argument("objective", help="The development objective")
    parser.add_argument(
        "--stage",
        choices=list(STAGE_COMMANDS.keys()),
        default="research",
        help="Stage to run (default: research)",
    )
    parser.add_argument("--research-doc", help="Path to existing research document")
    parser.add_argument("--plan-doc", help="Path to existing plan document")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    logs_dir = get_logs_dir()
    cleanup_old_logs(logs_dir)
    setup_logging(logs_dir, verbose=args.verbose)

    session = ClaudeSession()

    try:
        context = args.objective
        if args.research_doc:
            context += f"\n\nResearch document: {args.research_doc}"
        if args.plan_doc:
            context += f"\n\nPlan document: {args.plan_doc}"

        result = asyncio.run(run_stage(session, args.stage, context))
        print(result)

    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        logger.exception("Stage failed")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
