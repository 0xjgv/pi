"""Project directory management for π CLI."""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path

PI_GITIGNORE_ENTRY = ".π/\n"
DEFAULT_LOG_RETENTION_DAYS = 7
DEFAULT_DOCUMENT_RETENTION_DAYS = 5
ARCHIVED_BASE_DIR = "thoughts/shared/archived"
PROJECT_MARKERS = {
    ".git",
    "CLAUDE.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
}


def get_project_root(start_path: Path | None = None) -> Path:
    """Detect project root: CWD if has markers, else git root, else CWD.

    Args:
        start_path: Starting path for detection. Defaults to CWD.

    Returns:
        Detected project root path.
    """
    cwd = start_path or Path.cwd()

    # Check if CWD has project markers
    if any((cwd / m).exists() for m in PROJECT_MARKERS):
        return cwd

    # Fallback: git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Final fallback: CWD
    return cwd


def get_logs_dir(root: Path | None = None) -> Path:
    """Get logs directory, creating .π/logs/ if needed.

    Also adds `.π/` to the root .gitignore if not already present.

    Args:
        root: Root path where `.π/` should be created.
            Defaults to detected project root.

    Returns:
        Path to the logs directory.
    """
    root = root or get_project_root()
    logs_dir = root / ".π" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(root)
    return logs_dir


def cleanup_old_logs(
    logs_dir: Path, retention_days: int = DEFAULT_LOG_RETENTION_DAYS
) -> int:
    """Remove log files older than retention_days.

    Args:
        logs_dir: Directory containing log files.
        retention_days: Number of days to retain logs.

    Returns:
        Number of files deleted.
    """
    if not logs_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = 0

    for log_file in logs_dir.glob("*.log"):
        try:
            # Parse date from filename: YYYY-MM-DD-HH:MM.log
            date_str = log_file.stem[:10]  # Extract YYYY-MM-DD
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue  # Skip files with unexpected format

    return deleted


def archive_old_documents(
    *,
    root: Path | None = None,
    retention_days: int = DEFAULT_DOCUMENT_RETENTION_DAYS,
) -> dict[str, int]:
    """Archive research and plan documents older than retention_days.

    Moves files from thoughts/shared/{research,plans}/ to
    thoughts/shared/archived/{research,plans}/.

    Args:
        root: Project root path. Defaults to detected project root.
        retention_days: Number of days to retain documents before archiving.

    Returns:
        Dict with counts of archived files: {"research": N, "plans": M}
    """
    root = root or get_project_root()
    cutoff = datetime.now() - timedelta(days=retention_days)
    archived = {"research": 0, "plans": 0}

    for doc_type in ("research", "plans"):
        source_dir = root / "thoughts" / "shared" / doc_type
        archive_dir = root / ARCHIVED_BASE_DIR / doc_type

        if not source_dir.exists():
            continue

        for doc_file in source_dir.glob("*.md"):
            try:
                # Use file modification time for age calculation
                file_date = datetime.fromtimestamp(doc_file.stat().st_mtime)
                if file_date < cutoff:
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    doc_file.rename(archive_dir / doc_file.name)
                    archived[doc_type] += 1
            except OSError:
                continue  # Skip files with stat/permission errors

    return archived


def _ensure_gitignore(root: Path) -> None:
    """Add .π/ to root .gitignore if not already present."""
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".π" not in content:
            gitignore.write_text(content.rstrip("\n") + "\n" + PI_GITIGNORE_ENTRY)
    else:
        gitignore.write_text(PI_GITIGNORE_ENTRY)


def load_codebase_context(*, root: Path | None = None) -> str:
    """Load CLAUDE.md and dependencies for agent context.

    Provides codebase awareness to ReAct agents via signature instructions.
    Context is loaded once and shared across all workflow stages.

    Args:
        root: Project root path. Defaults to detected project root.

    Returns:
        Formatted context string with architecture and dependencies,
        or empty string if no context files found.
    """
    root = root or get_project_root()
    parts: list[str] = []

    # Load CLAUDE.md
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        parts.append(f"## Project Overview (CLAUDE.md)\n\n{claude_md.read_text()}")

    # Parse dependencies from pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if "dependencies = [" in content:
            start = content.index("dependencies = [")
            end = content.index("]", start) + 1
            deps_block = content[start:end]
            parts.append(f"## Dependencies\n\n```toml\n{deps_block}\n```")

    return "\n\n".join(parts)
