"""Hook event logging utilities."""

import json
from datetime import datetime
from pathlib import Path

# Initialize log directory
_home_dir = Path.home()
_LOG_DIR = _home_dir / ".claude" / "hook-logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_event(event: str, data: dict) -> None:
    """Log event to file with timestamp.

    Args:
        event: Event name/type (e.g., "[CHECK_COMMAND]", "[BLOCKED_COMMAND]")
        data: Event data to log (truncated to 200 chars in output)
    """
    now = datetime.now()
    log_file = _LOG_DIR / f"{now.strftime('%Y-%m-%d')}-hooks.log"
    with log_file.open("a") as f:
        f.write(
            f"{now.isoformat()} | {event} | {json.dumps(data, default=str)[:200]}\n"
        )
