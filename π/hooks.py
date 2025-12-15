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

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import cast

from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    HookJSONOutput,
)


# === Helper Functions ===
def _compact_path(path: Path | str) -> str:
    """
    Format a file path for readable console output.

    Applies these transformations in order:
    1. Replace home directory with ~/
    2. Replace current directory with ./
    3. Truncate long paths (>60 chars): /a/b/.../c/d

    Args:
        path: Absolute or relative file path

    Returns:
        Compact path string suitable for console output

    Examples:
        /Users/juan/project/src/main.py → ~/project/src/main.py
        /tmp/long/very/deep/path/file.py → /tmp/.../file.py
    """
    path = Path(path)
    home_dir = Path.home()

    # Try to make it relative to home directory
    try:
        if path.is_relative_to(home_dir):
            rel_path = path.relative_to(home_dir)
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
    """
    Find project root by traversing up the directory tree.

    Searches from start_path upward until finding a directory containing
    one of the specified marker files (e.g., package.json, Cargo.toml).

    Args:
        start_path: Starting directory to search from
        marker_files: List of filenames that indicate project root

    Returns:
        Path to project root directory, or None if not found

    Examples:
        >>> root = _find_project_root(Path("/project/src"), ["package.json"])
        >>> # Returns /project if /project/package.json exists
    """
    current = start_path
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent
    return None


# === Language Checkers ===
def check_python(path: Path) -> tuple[int, str]:
    """
    Run Python linting checks using Ruff.

    Invoked by: check_file_format() after Edit/Write/MultiEdit on .py/.pyx files

    Args:
        path: Absolute path to Python file to check

    Returns:
        (int, str) tuple:
        - int: Exit code (0 = success, 2 = failure)
        - str: Error output from ruff (empty string if success)

    Tool chain:
        1. Prefers: uvx ruff check [file]
        2. Fallback: ruff check [file]
        3. Unsupported: Prints warning, returns (0, "")

    Example:
        >>> exit_code, feedback = check_python(Path("main.py"))
        >>> if exit_code == 2:
        ...     print(f"Linting failed: {feedback}")
    """
    print(f"🐍 Running Python checks for {_compact_path(path)}...")

    # Ruff check - prefer uvx, fallback to ruff
    if shutil.which("uvx"):
        check_result = subprocess.run(
            ["uvx", "ruff", "check", str(path)],
            cwd=path.parent,
            capture_output=True,
            text=True,
        )
    elif shutil.which("ruff"):
        check_result = subprocess.run(
            ["ruff", "check", str(path)],
            cwd=path.parent,
            capture_output=True,
            text=True,
        )
    else:
        print("⚠️  Ruff not found")
        return (0, "")

    if check_result.returncode != 0:
        # Get the complete command output
        output = check_result.stderr or check_result.stdout
        return (2, output)

    print("✅ Python checks passed")
    return (0, "")


def check_typescript(path: Path) -> tuple[int, str]:
    """
    Run TypeScript/JavaScript linting checks using ESLint.

    Invoked by: check_file_format() after Edit/Write/MultiEdit on .ts/.tsx/.js/.jsx files

    Args:
        path: Absolute path to TypeScript/JavaScript file to check

    Returns:
        (int, str) tuple:
        - int: Exit code (0 = success, 2 = failure)
        - str: Error output from eslint (empty string if success)

    Requirements:
        - package.json must exist in parent directories
        - ESLint config must exist (.eslintrc.json, .eslintrc.js, etc.)

    Tool chain:
        1. Find project root via package.json
        2. Check for ESLint config files
        3. Run: npx eslint [file]
        4. Gracefully skip if no config found

    Example:
        >>> exit_code, feedback = check_typescript(Path("app.tsx"))
        >>> if exit_code == 2:
        ...     print(f"Linting failed: {feedback}")
    """
    project_root = _find_project_root(path.parent, ["package.json"])
    if not project_root:
        print(f"⚠️  No package.json found for {_compact_path(path)}")
        return (0, "")

    print(f"📦 Running TypeScript/JS checks for {_compact_path(path)}...")

    # ESLint check if config exists
    eslint_configs = [
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.cjs",
        "eslint.config.js",
    ]
    if any((project_root / config).exists() for config in eslint_configs):
        relative_path = path.relative_to(project_root)
        check_result = subprocess.run(
            ["npx", "eslint", str(relative_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    else:
        print("⚠️  No ESLint configuration found")
        return (0, "")

    if check_result.returncode != 0:
        # Get the complete command output
        output = check_result.stderr or check_result.stdout
        return (2, output)

    print("✅ TypeScript/JS checks passed")
    return (0, "")


def check_rust(path: Path) -> tuple[int, str]:
    """
    Run Rust compilation and type checks using Cargo.

    Invoked by: check_file_format() after Edit/Write/MultiEdit on .rs files

    Args:
        path: Absolute path to Rust file to check

    Returns:
        (int, str) tuple:
        - int: Exit code (0 = success, 2 = failure)
        - str: Error output from cargo check (empty string if success)

    Requirements:
        - Cargo.toml must exist in parent directories

    Tool chain:
        1. Find project root via Cargo.toml
        2. Run: cargo check (checks entire project)
        3. Gracefully skip if no Cargo.toml found

    Example:
        >>> exit_code, feedback = check_rust(Path("main.rs"))
        >>> if exit_code == 2:
        ...     print(f"Compilation failed: {feedback}")
    """
    project_root = _find_project_root(path.parent, ["Cargo.toml"])
    if not project_root:
        print(f"⚠️  No Cargo.toml found for {_compact_path(path)}")
        return (0, "")

    print(f"🦀 Running Rust checks for {_compact_path(path)}...")

    check_result = subprocess.run(
        ["cargo", "check"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if check_result.returncode != 0:
        # Get the complete command output
        output = check_result.stderr or check_result.stdout
        return (2, output)

    print("✅ Rust checks passed")
    return (0, "")


def check_go(path: Path) -> tuple[int, str]:
    """
    Run Go static analysis checks using go vet.

    Invoked by: check_file_format() after Edit/Write/MultiEdit on .go files

    Args:
        path: Absolute path to Go file to check

    Returns:
        (int, str) tuple:
        - int: Exit code (0 = success, 2 = failure)
        - str: Error output from go vet (empty string if success)

    Requirements:
        - go.mod must exist in parent directories

    Tool chain:
        1. Find project root via go.mod
        2. Run: go vet ./... (checks entire project)
        3. Gracefully skip if no go.mod found

    Example:
        >>> exit_code, feedback = check_go(Path("main.go"))
        >>> if exit_code == 2:
        ...     print(f"Static analysis failed: {feedback}")
    """
    project_root = _find_project_root(path.parent, ["go.mod"])
    if not project_root:
        print(f"⚠️  No go.mod found for {_compact_path(path)}")
        return (0, "")

    print(f"🔵 Running Go checks for {_compact_path(path)}...")

    # go vet is the standard Go static analysis tool
    check_result = subprocess.run(
        ["go", "vet", "./..."],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if check_result.returncode != 0:
        # Get the complete command output
        output = check_result.stderr or check_result.stdout
        return (2, output)

    print("✅ Go checks passed")
    return (0, "")


# Language registry mapping file extensions to checker functions
LANGUAGE_REGISTRY = {
    ".jsx": check_typescript,
    ".tsx": check_typescript,
    ".ts": check_typescript,
    ".js": check_typescript,
    ".pyx": check_python,
    ".py": check_python,
    ".rs": check_rust,
    ".go": check_go,
}


# === Hooks===
async def check_file_format(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """
    PostToolUse hook: Run language-specific linters after file modifications.

    Trigger: Fires after Edit, Write, or MultiEdit tools

    Behavior:
    1. Extracts file_path from tool_input
    2. Looks up language checker by file extension
    3. Runs language-specific linter (ruff, eslint, cargo check, go vet)
    4. If linter fails, blocks the operation and returns error feedback

    Input Structure (HookInput):
        {
            "tool_name": "Edit" | "Write" | "MultiEdit",
            "tool_input": {"file_path": "/path/to/file.py", ...}
        }

    Returns (HookJSONOutput):
        - {} if no checker or file doesn't exist (allow operation)
        - {} if linter passes (allow operation)
        - {"decision": "block", "reason": "...", "hookSpecificOutput": {...}}
          if linter fails (block operation, return error to agent)

    Supported files:
        - Python: .py, .pyx (via ruff)
        - TypeScript/JS: .ts, .tsx, .js, .jsx (via eslint)
        - Rust: .rs (via cargo check)
        - Go: .go (via go vet)

    Example flow:
        Agent runs: Edit(file_path="/src/main.py", new_string="...")
        Hook fires: check_file_format() extracts file_path
        Hook runs: ruff check /src/main.py
        Result: If ruff fails, hook returns block decision
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

    checker = LANGUAGE_REGISTRY.get(path.suffix.lower())
    if checker:
        print(f"🔍 Checking {_compact_path(path)} (triggered by {tool_name})")
        exit_code, feedback = checker(path)

        # If checks failed (exit code 2), block the operation and provide feedback
        if exit_code == 2:
            return cast(
                HookJSONOutput,
                {
                    "decision": "block",
                    "reason": f"Code quality checks failed for {path.name}",
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": feedback,
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

    Blocked patterns:
        - rm
        - rm -rf
        - rm -rf *
        - rm -rf **/*

    Behavior:
    1. Tokenizes bash command using shlex.split()
    2. Scans for blocked patterns in token sequence
    3. If pattern matched, denies execution with reason

    Input Structure (HookInput):
        {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /path", ...}
        }

    Returns (HookJSONOutput):
        - {} if command is safe (allow execution)
        - {"hookSpecificOutput": {"permissionDecision": "deny", ...}}
          if command contains blocked pattern (deny execution)

    Example flow:
        Agent tries: Bash(command="rm -rf temp/")
        Hook fires: check_bash_command() tokenizes command
        Hook finds: Pattern "rm -rf" in tokens
        Result: Hook denies execution with reason
    """
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]
    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")
    block_patterns = [
        ("rm",),
        ("rm", "-rf"),
        ("rm", "-rf", "*"),
        ("rm", "-rf", "**/*"),
    ]

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    for pattern_tokens in block_patterns:
        pattern_length = len(pattern_tokens)
        for idx in range(len(tokens) - pattern_length + 1):
            if tuple(tokens[idx : idx + pattern_length]) != pattern_tokens:
                continue

            matched_pattern = " ".join(pattern_tokens)
            print(f"[π-CLI] Blocked command: {command}")
            return cast(
                HookJSONOutput,
                {
                    "hookSpecificOutput": {
                        "permissionDecisionReason": f"Command contains invalid pattern: {matched_pattern}",
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                    }
                },
            )

    return {}


async def check_file_write(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """
    PreToolUse hook: Notify when a new file will be created.

    Trigger: Can fire before Write tool (currently not registered)

    Behavior:
        Checks if file exists; if not, returns allow decision with notification

    Input Structure (HookInput):
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "/path/to/new_file.py", ...}
        }

    Returns (HookJSONOutput):
        - {} if file already exists (silent allow)
        - {"decision": "allow", "reason": "File ... will be written"}
          if file doesn't exist (notify and allow)

    Note: This hook is defined but not currently registered in agent.py
    """
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    file_path = tool_input.get("file_path")
    if not file_path:
        return {}

    path = Path(file_path)
    if path.exists():
        return {}

    return cast(
        HookJSONOutput,
        {
            "decision": "allow",
            "reason": f"File {path.name} will be written",
        },
    )
