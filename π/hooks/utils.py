"""Utility functions for hook operations."""

import subprocess
from pathlib import Path

from π.hooks.logging import log_event

_home_dir = Path.home()


def compact_path(path: Path | str) -> str:
    """Format a file path for readable console output.

    Applies these transformations in order:
    1. Replace home directory with ~/
    2. Replace current directory with ./
    3. Truncate long paths (>60 chars): /a/b/.../c/d
    """
    path = Path(path)

    # Try to make it relative to home directory
    try:
        if path.is_relative_to(_home_dir):
            rel_path = path.relative_to(_home_dir)
            return f"~/{rel_path}"
    except (ValueError, AttributeError):
        pass

    # Try to make it relative to current directory
    try:
        rel_path = path.relative_to(Path.cwd())
        if str(rel_path) != str(path):
            return f"./{rel_path}"
    except ValueError:
        pass

    # If path is very long, show first and last parts
    path_str = str(path)
    if len(path_str) > 60:
        parts = path.parts
        if len(parts) > 4:
            # Use Path to join correctly for the platform
            return str(Path(parts[0], parts[1], "...", parts[-2], parts[-1]))

    return path_str


def find_project_root(start_path: Path, marker_files: list[str]) -> Path | None:
    """Find project root by traversing up the directory tree.

    Args:
        start_path: Starting directory to search from
        marker_files: List of filenames that indicate project root

    Returns:
        Path to project root, or None if not found
    """
    current = start_path
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent
    return None


def run_check_command(
    cwd: Path,
    cmd: list[str],
    name: str,
    tool_name: str | None = None,
    file_path: str | None = None,
) -> tuple[int, str, str]:
    """Run a check command and return raw results for processing.

    Args:
        cwd: Working directory to run command in
        cmd: Command and arguments as list
        name: Human-readable name for the checker
        tool_name: Optional tool that triggered this check
        file_path: Optional file path being checked

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    try:
        compact_file = compact_path(file_path) if file_path else "unknown"
        log_event(
            "[CHECK_COMMAND]",
            {
                "tool": tool_name or "unknown",
                "file": compact_file,
                "command": " ".join(cmd),
                "checker": name,
                "cwd": str(cwd),
            },
        )

        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            output = result.stderr or result.stdout
            log_event(
                "[CHECK_FAILED]",
                {
                    "reason": (output or "unknown"),
                    "exit_code": result.returncode,
                    "file": compact_file,
                    "checker": name,
                },
            )

        return (result.returncode, result.stdout, result.stderr)

    except subprocess.TimeoutExpired:
        return (124, "", f"{name} timed out")
    except FileNotFoundError:
        return (127, "", f"{name} not found")
    except Exception as e:
        return (1, "", f"{name} error: {e}")
