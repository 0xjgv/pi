"""Hook event logging utilities."""

import json
from datetime import datetime
from pathlib import Path

# Initialize log directory
_home_dir = Path.home()
_LOG_DIR = _home_dir / ".claude" / "hook-logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


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
