"""Language-specific code quality checkers."""

import shutil
from pathlib import Path

from π.hooks.registry import language_checker
from π.hooks.utils import compact_path, console, find_project_root, run_check_command


@language_checker([".py", ".pyx"])
def check_python(path: Path, tool_name: str | None = None) -> int:
    """Run Python checks using ruff."""
    console.print(f"🐍 Running Python checks for {compact_path(path)}...")

    if shutil.which("uvx"):
        cmd = ["uvx", "ruff", "check", str(path)]
    elif shutil.which("ruff"):
        cmd = ["ruff", "check", str(path)]
    else:
        console.print("⚠️  Ruff not found")
        return 0

    exit_code, stdout, stderr = run_check_command(
        cwd=path.parent,
        cmd=cmd,
        name="ruff",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            console.print(output, end="")
        return 2

    console.print("✅ Python checks passed")
    return 0


@language_checker([".ts", ".tsx", ".js", ".jsx"])
def check_typescript(path: Path, tool_name: str | None = None) -> int:
    """Run TypeScript/JavaScript checks using ESLint."""
    project_root = find_project_root(path.parent, ["package.json"])
    if not project_root:
        console.print(f"⚠️  No package.json found for {compact_path(path)}")
        return 0

    console.print(f"📦 Running TypeScript/JS checks for {compact_path(path)}...")

    eslint_configs = [
        "eslint.config.mjs",
        "eslint.config.js",
        ".eslintrc.json",
        ".eslintrc.js",
        ".eslintrc.cjs",
    ]
    if not any((project_root / config).exists() for config in eslint_configs):
        console.print("⚠️  No ESLint configuration found")
        return 0

    relative_path = path.relative_to(project_root)
    exit_code, stdout, stderr = run_check_command(
        cwd=project_root,
        cmd=["npx", "eslint", str(relative_path)],
        name="eslint",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            console.print(output, end="")
        return 2

    console.print("✅ TypeScript/JS checks passed")
    return 0


@language_checker([".rs"], scope="project", project_markers=["Cargo.toml"])
def check_rust(path: Path, tool_name: str | None = None) -> int:
    """Run Rust checks using cargo check."""
    project_root = find_project_root(path.parent, ["Cargo.toml"])
    if not project_root:
        console.print(f"⚠️  No Cargo.toml found for {compact_path(path)}")
        return 0

    console.print(f"🦀 Running Rust checks for {compact_path(path)}...")

    exit_code, stdout, stderr = run_check_command(
        cwd=project_root,
        cmd=["cargo", "check"],
        name="cargo check",
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            console.print(output, end="")
        return 2

    console.print("✅ Rust checks passed")
    return 0


@language_checker([".go"], scope="project", project_markers=["go.mod"])
def check_go(path: Path, tool_name: str | None = None) -> int:
    """Run Go checks using golangci-lint (preferred) or go vet (fallback)."""
    project_root = find_project_root(path.parent, ["go.mod"])
    if not project_root:
        console.print(f"⚠️  No go.mod found for {compact_path(path)}")
        return 0

    console.print(f"🔵 Running Go checks for {compact_path(path)}...")

    # Prefer golangci-lint, fall back to go vet
    if shutil.which("golangci-lint"):
        cmd = ["golangci-lint", "run", "./..."]
        name = "golangci-lint"
    else:
        cmd = ["go", "vet", "./..."]
        name = "go vet"

    exit_code, stdout, stderr = run_check_command(
        cwd=project_root,
        cmd=cmd,
        name=name,
        tool_name=tool_name,
        file_path=str(path),
    )

    if exit_code != 0:
        output = stderr or stdout
        if output:
            console.print(output, end="")
        return 2

    console.print("✅ Go checks passed")
    return 0
