"""Project directory management for π CLI."""

from pathlib import Path

PI_GITIGNORE_ENTRY = ".π/\n"


def get_logs_dir(root: Path | None = None) -> Path:
    """Get logs directory, creating .π/logs/ if needed.

    Also adds `.π/` to the root .gitignore if not already present.

    Args:
        root: Root path where `.π/` should be created.
            Defaults to current working directory.

    Returns:
        Path to the logs directory.
    """
    root = root or Path.cwd()
    logs_dir = root / ".π" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(root)
    return logs_dir


def _ensure_gitignore(root: Path) -> None:
    """Add .π/ to root .gitignore if not already present."""
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".π" not in content:
            gitignore.write_text(content.rstrip("\n") + "\n" + PI_GITIGNORE_ENTRY)
    else:
        gitignore.write_text(PI_GITIGNORE_ENTRY)
