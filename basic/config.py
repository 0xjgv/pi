"""Configuration for basic workflow module.

This module provides agent options and command mapping, making basic/
independent from π.config and π.workflow.context.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from π.core.enums import Command
from π.hooks import check_bash_command, check_file_format
from π.support import can_use_tool
from π.support.directory import get_project_root

logger = logging.getLogger(__name__)

# Default logs directory (relative to project root)
LOGS_DIR_NAME = ".π/logs"

# Project root for command discovery
PROJECT_ROOT = Path(__file__).parent.parent

# https://code.claude.com/docs/en/settings#tools-available-to-claude
ALL_AVAILABLE_TOOLS = [
    "AskUserQuestion",
    "Bash",
    "Edit",
    "ExitPlanMode",
    "Glob",
    "Grep",
    "KillShell",
    "MCPSearch",
    "NotebookEdit",
    "Read",
    "Skill",
    "Task",
    "TaskOutput",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
    "Write",
]

ORCHESTRATOR_TOOLS = [
    "MCPSearch",
    "Grep",
    "Glob",
    "Read",
    "Skill",
    "Task",
    "TaskOutput",
    "TodoWrite",
]


STAGE_AGENT_TOOLS = [t for t in ALL_AVAILABLE_TOOLS if t not in "AskUserQuestion"]


def build_command_map(
    *,
    command_dir: Path | None = None,
) -> dict[Command, str]:
    """Build a command map from the command directory.

    Args:
        command_dir: Directory containing command files. Defaults to .claude/commands.

    Returns:
        Mapping of Command enum to slash command string.
    """
    if command_dir is None:
        command_dir = PROJECT_ROOT / ".claude/commands"

    command_map: dict[Command, str] = {}
    if not command_dir.exists():
        logger.warning("Command directory not found: %s", command_dir)
        return command_map

    # Numbered commands (existing pattern: 1_research_codebase.md)
    for f in sorted(command_dir.glob("[0-9]_*.md")):
        try:
            # e.g., '1_research_codebase' -> 'RESEARCH_CODEBASE'
            command_name = f.stem.split("_", 1)[1].upper()
            if command_enum_member := getattr(Command, command_name, None):
                command_map[command_enum_member] = f"/{f.stem}"
        except (IndexError, AttributeError):
            logger.warning("Skipping malformed command file: %s", f.name)

    # Non-numbered commands (explicit mapping)
    non_numbered = {
        Command.WRITE_CLAUDE_MD: "write-claude-md",
    }
    for cmd, filename in non_numbered.items():
        cmd_file = command_dir / f"{filename}.md"
        if cmd_file.exists():
            command_map[cmd] = f"/{filename}"

    return command_map


# Module-level command map (built once at import time)
COMMAND_MAP: dict[Command, str] = build_command_map()


def get_agent_options(
    *,
    system_prompt: str | None = None,
    cwd: Path | None = None,
) -> ClaudeAgentOptions:
    """Get Claude agent options with hooks and permissions configured.

    Args:
        system_prompt: Optional system prompt override.
        cwd: Working directory for the agent. Defaults to project root.

    Returns:
        Configured ClaudeAgentOptions instance.
    """
    cwd = cwd or get_project_root()
    return ClaudeAgentOptions(
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[check_file_format]),
            ],
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[check_bash_command]),
            ],
        },
        permission_mode="acceptEdits",
        allowed_tools=ALL_AVAILABLE_TOOLS,
        system_prompt=system_prompt,
        setting_sources=["project"],
        can_use_tool=can_use_tool,
        cwd=cwd,
    )


def get_logs_dir() -> Path:
    """Get the logs directory, creating it if necessary.

    Returns:
        Path to the logs directory.
    """
    logs_dir = get_project_root() / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logging(log_dir: Path, *, verbose: bool = False) -> Path:
    """Configure file logging for basic workflow.

    Sets up Python's logging module with a file handler to capture debug logs
    from bridge.py, tools.py, and other basic.* modules.

    Args:
        log_dir: Directory to store log files.
        verbose: If True, also log DEBUG messages to console.

    Returns:
        Path to the log file.
    """
    # Get the basic namespace logger
    basic_logger = logging.getLogger("basic")
    basic_logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    log_path = log_dir / f"basic-{timestamp}.log"

    # File handler for DEBUG-level logging
    file_handler = logging.FileHandler(log_path, delay=True)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    basic_logger.addHandler(file_handler)

    # Optional console handler for verbose mode
    if verbose:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )
        basic_logger.addHandler(console_handler)

    # Allow DEBUG messages through
    basic_logger.setLevel(logging.DEBUG)

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return log_path
