import uuid
from functools import wraps
from os import getpid, system
from pathlib import Path

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    TextBlock,
    UserMessage,
)


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


def escape_csv_text(text: str) -> str:
    # Replace quotes with double quotes and wrap in quotes to escape commas
    return f'"{text.strip().replace('"', '""')}"'


def write_to_log(log_file: Path, content: str) -> None:
    """Append content to a log file.

    Args:
        log_file: Path to the log file
        content: Content to append
    """
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")


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


def load_claude_commands() -> list[str]:
    """Load Claude commands from the commands directory.

    Returns:
        An ordered list of command names
    """
    commands_dir = Path.cwd() / ".claude" / "commands"
    if not commands_dir.exists():
        raise FileNotFoundError(f"Commands directory not found: {commands_dir}")
    return sorted(command_file.stem for command_file in commands_dir.glob("*.md"))
