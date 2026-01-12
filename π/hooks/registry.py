"""Language checker registry system."""

from collections.abc import Callable
from pathlib import Path

# Type alias for checker functions
CheckerFunc = Callable[[Path, str | None], int]

# Global registry of language checkers by file extension
_registry: dict[str, CheckerFunc] = {}


def language_checker(
    extensions: list[str],
    scope: str = "file",  # noqa: ARG001 - kept for API compatibility
    project_markers: list[str] | None = None,  # noqa: ARG001
) -> Callable[[CheckerFunc], CheckerFunc]:
    """Decorator to register functions as language checkers.

    Args:
        extensions: List of file extensions to handle (e.g., ['.py', '.pyx'])
        scope: Unused, kept for API compatibility
        project_markers: Unused, kept for API compatibility

    Returns:
        Decorator function
    """

    def decorator(func: CheckerFunc) -> CheckerFunc:
        for ext in extensions:
            _registry[ext.lower()] = func
        return func

    return decorator


def get_checker(extension: str) -> CheckerFunc | None:
    """Get the checker for a file extension.

    Args:
        extension: File extension including dot (e.g., '.py')

    Returns:
        Checker function if registered, None otherwise
    """
    return _registry.get(extension.lower())
