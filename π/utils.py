import json
import logging
import uuid
from datetime import datetime
from functools import wraps
from os import getpid, system
from pathlib import Path
from typing import Any

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    TextBlock,
    UserMessage,
)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the π CLI.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level

    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("π")


def generate_workflow_id() -> str:
    """Generate a unique UUID for a workflow run.

    Returns:
        A UUID string to identify the workflow run
    """
    return str(uuid.uuid4())


def create_workflow_dir(base_dir: Path, workflow_id: str) -> Path:
    """Create a log directory for a workflow run.

    Args:
        base_dir: Base directory (typically .logs or /thoughts)
        workflow_id: The UUID of the workflow run

    Returns:
        Path to the created workflow directory
    """
    dir_path = base_dir / workflow_id
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def log_workflow_event(workflow_dir: Path, event: str, data: dict[str, Any]) -> None:
    """Log a workflow event to the log file.

    Args:
        workflow_dir: The workflow log directory
        event: Event name (e.g., "stage_start", "question_loop", "review")
        data: Event data to log
    """
    log_file = workflow_dir / "workflow.jsonl"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        **data,
    }
    with log_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def prevent_sleep(func):
    """Prevents the system from sleeping while the function is running"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        pid = getpid()
        system(f"caffeinate -disuw {pid}&")
        return func(*args, **kwargs)

    return wrapper


def extract_message_content(msg: Message | ResultMessage) -> str | None:
    if isinstance(msg, ResultMessage):
        return msg.result
    if isinstance(msg, (UserMessage, AssistantMessage)):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
            return "\n".join(texts) if len(texts) > 0 else None
        return None
    return None
