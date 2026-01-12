"""Language-specific code quality checkers."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from π.console import console
from π.hooks.registry import language_checker
from π.hooks.utils import compact_path, find_project_root, run_check_command


@dataclass
class CheckerConfig:
    """Configuration for a language checker."""

    emoji: str
    language: str
    project_markers: list[str]
    get_command: Callable[[Path, Path | None], tuple[list[str], str] | None]


def _run_checker(path: Path, config: CheckerConfig) -> int:
    """Run a checker with the given configuration.

    Args:
        path: File path to check
        config: Checker configuration

    Returns:
        Exit code (0=success, 2=failure)
    """
    project_root = None
    if config.project_markers:
        project_root = find_project_root(path.parent, config.project_markers)
        if not project_root:
            markers = ", ".join(config.project_markers)
            console.print(f"⚠️  No {markers} found for {compact_path(path)}")
            return 0

    console.print(
        f"{config.emoji} Running {config.language} checks for {compact_path(path)}..."
    )

    cmd_result = config.get_command(path, project_root)
    if cmd_result is None:
        return 0

    cmd, name = cmd_result
    cwd = project_root or path.parent

    exit_code, stdout, stderr = run_check_command(cwd=cwd, cmd=cmd, name=name)

    if exit_code != 0:
        output = stderr or stdout
        if output:
            console.print(output, end="")
        return 2

    console.print(f"✅ {config.language} checks passed")
    return 0


# --- Command builders ---


def _python_command(path: Path, _project_root: Path | None) -> tuple[list[str], str]:
    if shutil.which("uvx"):
        return ["uvx", "ruff", "check", "--fix", str(path)], "ruff"
    if shutil.which("ruff"):
        return ["ruff", "check", "--fix", str(path)], "ruff"
    console.print("⚠️  Ruff not found")
    return None  # type: ignore[return-value]


def _typescript_command(
    path: Path,
    project_root: Path | None,
) -> tuple[list[str], str] | None:
    if not project_root:
        return None

    eslint_configs = [
        "eslint.config.mjs",
        "eslint.config.js",
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.cjs",
    ]
    if not any((project_root / config).exists() for config in eslint_configs):
        console.print("⚠️  No ESLint configuration found")
        return None

    relative_path = path.relative_to(project_root)
    return ["npx", "eslint", str(relative_path)], "eslint"


def _rust_command(_path: Path, _project_root: Path | None) -> tuple[list[str], str]:
    return ["cargo", "check"], "cargo check"


def _go_command(_path: Path, _project_root: Path | None) -> tuple[list[str], str]:
    if shutil.which("golangci-lint"):
        return ["golangci-lint", "run", "./..."], "golangci-lint"
    return ["go", "vet", "./..."], "go vet"


# --- Checker configurations ---

_PYTHON = CheckerConfig(
    emoji="🐍",
    language="Python",
    project_markers=[],
    get_command=_python_command,
)

_TYPESCRIPT = CheckerConfig(
    emoji="📦",
    language="TypeScript/JS",
    project_markers=["package.json"],
    get_command=_typescript_command,
)

_RUST = CheckerConfig(
    emoji="🦀",
    language="Rust",
    project_markers=["Cargo.toml"],
    get_command=_rust_command,
)

_GO = CheckerConfig(
    emoji="🔵",
    language="Go",
    project_markers=["go.mod"],
    get_command=_go_command,
)


# --- Registered checkers ---


@language_checker([".py", ".pyx"])
def check_python(path: Path, _tool_name: str | None = None) -> int:
    """Run Python checks using ruff."""
    return _run_checker(path, _PYTHON)


@language_checker([".ts", ".tsx", ".js", ".jsx"])
def check_typescript(path: Path, _tool_name: str | None = None) -> int:
    """Run TypeScript/JavaScript checks using ESLint."""
    return _run_checker(path, _TYPESCRIPT)


@language_checker([".rs"], scope="project", project_markers=["Cargo.toml"])
def check_rust(path: Path, _tool_name: str | None = None) -> int:
    """Run Rust checks using cargo check."""
    return _run_checker(path, _RUST)


@language_checker([".go"], scope="project", project_markers=["go.mod"])
def check_go(path: Path, _tool_name: str | None = None) -> int:
    """Run Go checks using golangci-lint (preferred) or go vet (fallback)."""
    return _run_checker(path, _GO)
