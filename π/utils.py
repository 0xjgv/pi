import importlib
import re
import uuid
from functools import wraps
from os import getpid, system
from pathlib import Path


def load_prompt(step_name: str) -> tuple[str, str | None]:
    """Dynamically import a prompt module and extract its exports.

    Args:
        step_name: Name of the prompt (e.g., 'research_codebase')

    Returns:
        Tuple of (prompt_template, model_name)

    Raises:
        ImportError: If prompt module doesn't exist
        AttributeError: If module missing required 'prompt' attribute
    """
    try:
        # Use Python's import system for proper caching and validation
        module = importlib.import_module(f"π.prompts.{step_name}")

        # Validate required attribute exists
        if not hasattr(module, "prompt"):
            raise AttributeError(
                f"Prompt module '{step_name}' missing required 'prompt' attribute"
            )

        # Extract exports with type validation
        prompt = module.prompt
        model = getattr(module, "model", None)

        if not isinstance(prompt, str):
            raise TypeError(f"Expected 'prompt' to be str, got {type(prompt)}")

        if model is not None and not isinstance(model, str):
            raise TypeError(f"Expected 'model' to be str or None, got {type(model)}")

        return prompt, model

    except ImportError as e:
        raise ImportError(
            f"Prompt module 'π.prompts.{step_name}' not found. "
            f"Available prompts: research_codebase, create_plan, iterate_plan, etc."
        ) from e


def extract_existing_files(text: str) -> list[str]:
    """Extract all existing file paths from a text string.

    Looks for file paths within the text by:
    1. Checking if the entire string is a file path
    2. Extracting path-like patterns from the text
    3. Verifying if any of those paths exist

    Returns:
        List of existing file paths found in the text (as strings)
    """
    text = text.strip()
    if not text:
        return []

    existing_files = []

    # First, check if the entire string is a file path
    if Path(text).exists():
        return [text]

    # Extract potential file paths from the text
    # Look for:
    # - Absolute paths starting with /
    # - Relative paths like ./path or ../path
    # - Paths with slashes that look like file system paths
    path_patterns = [
        r"(?:^|\s)(/[^\s]+)",  # Absolute paths
        r"(?:^|\s)(\.\.?/[^\s]+)",  # Relative paths (./ or ../)
        r"(?:^|\s)([^\s/]+/[^\s]+)",  # Path-like strings with slashes
    ]

    checked_paths = set()

    for pattern in path_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            potential_path = match.group(1).strip()
            # Clean up common trailing punctuation
            potential_path = re.sub(r"[,:;.!?]+$", "", potential_path)

            if potential_path not in checked_paths:
                checked_paths.add(potential_path)
                if Path(potential_path).exists():
                    existing_files.append(potential_path)

    return existing_files


def extract_file_containing(text: str, substring: str) -> str | None:
    """Extract a single existing file path that contains a specific substring.

    Args:
        text: The text to search for file paths
        substring: The substring to search for within file paths

    Returns:
        The first existing file path containing the substring, or None if not found

    Note:
        If multiple files contain the substring, only the first one is returned.
        Use extract_files_containing() to get all matching files.
    """
    existing_files = extract_existing_files(text)

    for file_path in existing_files:
        if substring in file_path:
            return file_path

    return None


def extract_files_containing(text: str, substring: str) -> list[str]:
    """Extract all existing file paths that contain a specific substring.

    Args:
        text: The text to search for file paths
        substring: The substring to search for within file paths

    Returns:
        List of existing file paths containing the substring (may be empty)
    """
    existing_files = extract_existing_files(text)
    return [file_path for file_path in existing_files if substring in file_path]


def contains_existing_file(text: str) -> bool:
    """Check if the string contains any existing file path.

    Looks for file paths within the text by:
    1. Checking if the entire string is a file path
    2. Extracting path-like patterns from the text
    3. Verifying if any of those paths exist
    """
    return len(extract_existing_files(text)) > 0


def generate_workflow_id() -> str:
    """Generate a unique UUID for a workflow run.

    Returns:
        A UUID string to identify the workflow run
    """
    return str(uuid.uuid4())


def create_workflow_log_dir(base_dir: Path, workflow_id: str) -> Path:
    """Create a log directory for a workflow run.

    Args:
        base_dir: Base directory (typically .logs)
        workflow_id: The UUID of the workflow run

    Returns:
        Path to the created workflow log directory
    """
    log_dir = base_dir / workflow_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


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
