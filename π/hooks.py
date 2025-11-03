import shutil
import subprocess
from pathlib import Path
from typing import cast

from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    HookJSONOutput,
)


async def check_bash_command(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """Prevent certain bash commands from being executed."""
    if "tool_input" not in input_data or "tool_name" not in input_data:
        return {}

    tool_input = input_data["tool_input"]
    tool_name = input_data["tool_name"]
    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")
    block_patterns = ["rm", "rm -rf", "rm -rf *", "rm -rf **/*"]

    for pattern in block_patterns:
        if command.startswith(pattern) or pattern in command:
            print(f"[π-CLI] Blocked command: {command}")
            return cast(
                HookJSONOutput,
                {
                    "hookSpecificOutput": {
                        "permissionDecisionReason": f"Command contains invalid pattern: {pattern}",
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                    }
                },
            )

    return {}


# === Helper Functions ===


def _compact_path(path: Path | str) -> str:
    """Make a path more compact for display."""
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
    """Find project root by looking for marker files."""
    current = start_path
    while current != current.parent:
        for marker in marker_files:
            if (current / marker).exists():
                return current
        current = current.parent
    return None


# === Language Checkers ===


def check_python(path: Path) -> tuple[int, str]:
    """Run Python-specific checks - ruff only."""
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
    """Run TypeScript/JavaScript checks - ESLint only."""
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
    """Run Rust checks."""
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
    """Run Go checks."""
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
    ".py": check_python,
    ".pyx": check_python,
    ".ts": check_typescript,
    ".tsx": check_typescript,
    ".js": check_typescript,
    ".jsx": check_typescript,
    ".rs": check_rust,
    ".go": check_go,
}


async def check_file_format(
    input_data: HookInput, _tool_use_id: str | None, _context: HookContext
) -> HookJSONOutput:
    """Run checks on modified files based on file type."""
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
