"""Project directory management for π CLI."""

from datetime import datetime, timedelta
from pathlib import Path

PI_GITIGNORE_ENTRY = ".π/\n"
DEFAULT_LOG_RETENTION_DAYS = 7


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


def _ensure_gitignore(root: Path) -> None:
    """Add .π/ to root .gitignore if not already present."""
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".π" not in content:
            gitignore.write_text(content.rstrip("\n") + "\n" + PI_GITIGNORE_ENTRY)
    else:
        gitignore.write_text(PI_GITIGNORE_ENTRY)
