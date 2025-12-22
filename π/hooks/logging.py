"""Hook event logging utilities."""

import json
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_HOOK_LOG_RETENTION_DAYS = 30

# Initialize log directory
_home_dir = Path.home()
_LOG_DIR = _home_dir / ".claude" / "hook-logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


# Cleanup happens after the function definition below


def cleanup_old_hook_logs(retention_days: int = DEFAULT_HOOK_LOG_RETENTION_DAYS) -> int:
    """Remove hook log files older than retention_days.

    Args:
        retention_days: Number of days to retain logs.

    Returns:
        Number of files deleted.
    """
    if not _LOG_DIR.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = 0

    for log_file in _LOG_DIR.glob("*-hooks.log"):
        try:
            # Parse date from filename: YYYY-MM-DD-hooks.log
            date_str = log_file.stem[:10]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                deleted += 1
        except (ValueError, OSError):
            continue

    return deleted


def _truncate_value(value: object, max_len: int = 200) -> object:
    """Truncate string values, preserving other types."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "..."
    if isinstance(value, dict):
        return {k: _truncate_value(v, max_len) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_value(v, max_len) for v in value]
    return value


def log_event(event: str, data: dict) -> None:
    """Log event to file with timestamp.

    Args:
        event: Event name/type (e.g., "[CHECK_COMMAND]", "[BLOCKED_COMMAND]")
        data: Event data to log (string values truncated to 200 chars)
    """
    now = datetime.now()
    log_file = _LOG_DIR / f"{now.strftime('%Y-%m-%d')}-hooks.log"
    truncated = _truncate_value(data)
    with log_file.open("a") as f:
        f.write(f"{now.isoformat()} | {event} | {json.dumps(truncated, default=str)}\n")


# Clean old logs on module import
cleanup_old_hook_logs()
