import importlib
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
