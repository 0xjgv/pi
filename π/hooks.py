"""
Hook validation system for Claude Agent SDK tool execution.

This module implements pre- and post-execution validation hooks that:
- PreToolUse: Intercept tool calls before execution (blocks dangerous commands)
- PostToolUse: Validate tool outputs after execution (runs code quality checks)

Hooks return structured JSON responses following the Claude Agent SDK spec:
- Empty dict {} means "no action needed, proceed normally"
- HookJSONOutput with "decision": "block" blocks the operation
- HookJSONOutput with "permissionDecision": "deny" denies execution

Hook Flow:
  Tool called → PreToolUse hooks → Tool executes → PostToolUse hooks → Result
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, cast

from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    HookJSONOutput,
)


# === Global Registry ===
@dataclass
class LanguageChecker:
    """Metadata for a language checker."""

    func: Callable[[Path, str | None], int]
    scope: str  # "file" or "project"
    project_markers: list[str]


_language_registry: dict[str, LanguageChecker] = {}

# Initialize log directory
_home_dir = Path.home()
_log_dir = _home_dir / ".claude" / "hook-logs"
_log_dir.mkdir(parents=True, exist_ok=True)


# === Decorators ===
def language_checker(
    extensions: list[str],
    scope: str = "file",
    project_markers: list[str] | None = None,
) -> Callable:
    """
    Decorator to register functions as language checkers.

    Args:
        extensions: List of file extensions to handle (e.g., ['.py', '.pyx'])
        scope: "file" for per-file checks, "project" for project-wide checks
        project_markers: For project-scope, files that identify project root
    """

    def decorator(func: Callable) -> Callable:
        checker = LanguageChecker(
            func=func,
            scope=scope,
            project_markers=project_markers or [],
        )
        for ext in extensions:
            _language_registry[ext.lower()] = checker
        return func

    return decorator


# === Helper Functions ===
def _compact_path(path: Path | str) -> str:
    """
    Format a file path for readable console output.

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
        parts = path_str.split("/")
        if len(parts) > 4:
            return f"{'/'.join(parts[:2])}/.../{'/'.join(parts[-2:])}"

    return path_str


def _find_project_root(start_path: Path, marker_files: list[str]) -> Path | None:
    """Find project root by traversing up the directory tree."""
    current = start_path
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent
    return None


def _log_event(event: str, data: dict) -> None:
    """Log event to file with timestamp."""
    now = datetime.now()
    log_file = _log_dir / f"{now.strftime('%d-%m-%Y')}-hooks.log"
    with log_file.open("a") as f:
        f.write(
            f"{now.isoformat()} | {event} | {json.dumps(data, default=str)[:200]}\n"
        )


def _run_check_command(
    cwd: Path,
    cmd: list[str],
    name: str,
    tool_name: str | None = None,
    file_path: str | None = None,
) -> tuple[int, str, str]:
    """
    Run a check command and return raw results for processing.

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    try:
        compact_file = _compact_path(file_path) if file_path else "unknown"
        _log_event(
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
            _log_event(
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


def _is_dangerous_command(cmd: str) -> bool:
    """Check if a bash command is potentially dangerous."""
    dangerous_patterns = [
        (r"rm\s+-rf\s+(/|~)", "Dangerous rm -rf command detected!"),
        (r"(curl|wget).*\|.*sh", "Piping curl/wget to shell is not allowed!"),
        (r"dd\s+if=.*of=/dev/", "Direct disk write operation detected!"),
        (r"mkfs\.\w+", "File system formatting command detected!"),
        (r"fdisk\s+/dev/", "Disk partitioning command detected!"),
        (r">\s*/dev/sd[a-z]", "Direct write to disk device detected!"),
    ]

    for pattern, _ in dangerous_patterns:
        if re.search(pattern, cmd):
            return True

    simple_patterns = ["format c:", "rm -rf *"]
    return any(pattern in cmd.lower() for pattern in simple_patterns)


# === Language Checkers ===
@language_checker([".py", ".pyx"])
def check_python(path: Path, tool_name: str | None = None) -> int:
    """Run Python checks using ruff."""
    print(f"🐍 Running Python checks for {_compact_path(path)}...")

    if shutil.which("uvx"):
        cmd = ["uvx", "ruff", "check", str(path)]
    elif shutil.which("ruff"):
        cmd = ["ruff", "check", str(path)]
    else:
        print("⚠️  Ruff not found")
        return 0

    exit_code, stdout, stderr = _run_check_command(
        cwd=path.parent,
        cmd=cmd,
        name="ruff",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            print(output, end="")
        return 2

    print("✅ Python checks passed")
    return 0


@language_checker([".ts", ".tsx", ".js", ".jsx"])
def check_typescript(path: Path, tool_name: str | None = None) -> int:
    """Run TypeScript/JavaScript checks using ESLint."""
    project_root = _find_project_root(path.parent, ["package.json"])
    if not project_root:
        print(f"⚠️  No package.json found for {_compact_path(path)}")
        return 0

    print(f"📦 Running TypeScript/JS checks for {_compact_path(path)}...")

    eslint_configs = [
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.cjs",
        "eslint.config.js",
    ]
    if not any((project_root / config).exists() for config in eslint_configs):
        print("⚠️  No ESLint configuration found")
        return 0

    relative_path = path.relative_to(project_root)
    exit_code, stdout, stderr = _run_check_command(
        cwd=project_root,
        cmd=["npx", "eslint", str(relative_path)],
        name="eslint",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            print(output, end="")
        return 2

    print("✅ TypeScript/JS checks passed")
    return 0


@language_checker([".rs"], scope="project", project_markers=["Cargo.toml"])
def check_rust(path: Path, tool_name: str | None = None) -> int:
    """Run Rust checks using cargo check."""
    project_root = _find_project_root(path.parent, ["Cargo.toml"])
    if not project_root:
        print(f"⚠️  No Cargo.toml found for {_compact_path(path)}")
        return 0

    print(f"🦀 Running Rust checks for {_compact_path(path)}...")

    exit_code, stdout, stderr = _run_check_command(
        cwd=project_root,
        cmd=["cargo", "check"],
        name="cargo check",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            print(output, end="")
        return 2

    print("✅ Rust checks passed")
    return 0


@language_checker([".go"], scope="project", project_markers=["go.mod"])
def check_go(path: Path, tool_name: str | None = None) -> int:
    """Run Go checks using golangci-lint (preferred) or go vet (fallback)."""
    project_root = _find_project_root(path.parent, ["go.mod"])
    if not project_root:
        print(f"⚠️  No go.mod found for {_compact_path(path)}")
        return 0

    print(f"🔵 Running Go checks for {_compact_path(path)}...")

    # Prefer golangci-lint, fall back to go vet
    if shutil.which("golangci-lint"):
        cmd = ["golangci-lint", "run", "./..."]
        name = "golangci-lint"
    else:
        cmd = ["go", "vet", "./..."]
        name = "go vet"

    exit_code, stdout, stderr = _run_check_command(
        cwd=project_root,
        cmd=cmd,
        name=name,
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            print(output, end="")
        return 2

    print("✅ Go checks passed")
    return 0


# === Hooks===
async def check_file_format(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """
    PostToolUse hook: Run language-specific linters after file modifications.

    Trigger: Fires after Edit, Write, or MultiEdit tools
    """
    tool_name = input_data.get("tool_name")

    # Only check files modified by Edit, Write, or MultiEdit tools
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return {}

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path")
    if not file_path:
        return {}

    path = Path(file_path)
    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    checker_info = _language_registry.get(suffix)
    if checker_info:
        print(f"🔍 Checking {_compact_path(path)} (triggered by {tool_name})")

        # Run the checker
        exit_code = checker_info.func(path, tool_name)

        # Log the check result
        _log_event(
            "[LANGUAGE_CHECK]",
            {
                "result": "passed" if exit_code == 0 else "failed",
                "tool": tool_name or "unknown",
                "file": _compact_path(path),
                "exit_code": exit_code,
                "checker": suffix,
            },
        )

        # If checks failed (exit code 2), block the operation
        if exit_code == 2:
            return cast(
                HookJSONOutput,
                {
                    "decision": "block",
                    "reason": f"Code quality checks failed for {path.name}",
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                    },
                },
            )

    return {}


async def check_bash_command(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """
    PreToolUse hook: Block dangerous bash commands before execution.

    Trigger: Fires before Bash tool executes

    Blocked patterns (regex-based):
        - rm -rf / or ~
        - curl/wget piped to shell
        - dd writing to /dev/
        - mkfs commands
        - fdisk commands
        - Direct writes to /dev/sd*
        - rm -rf *
        - format c:
    """
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]
    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")

    if _is_dangerous_command(command):
        print(f"🚫 Blocked dangerous command: {command}")
        _log_event(
            "[BLOCKED_COMMAND]",
            {
                "command": command,
                "reason": "Dangerous pattern detected",
            },
        )
        return cast(
            HookJSONOutput,
            {
                "hookSpecificOutput": {
                    "permissionDecisionReason": "Command blocked: Potentially dangerous operation",
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                }
            },
        )

    return {}
