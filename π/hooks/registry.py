"""Language checker registry system."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar


class CheckerFunc(Protocol):
    """Protocol for language checker functions with optional tool_name."""

    def __call__(self, path: Path, _tool_name: str | None = None) -> int:
        """Check a file for issues.

        Args:
            path: Path to the file to check.
            _tool_name: Optional name of the tool that triggered the check.

        Returns:
            Exit code (0 = pass, non-zero = issues found).
        """
        ...


_F = TypeVar("_F", bound=CheckerFunc)

# Global registry of language checkers by file extension
_registry: dict[str, CheckerFunc] = {}


def language_checker(
    extensions: list[str],
) -> Callable[[_F], _F]:
    """Decorator to register functions as language checkers.

    Args:
        extensions: List of file extensions to handle (e.g., ['.py', '.pyx'])

    Returns:
        Decorator function
    """

    def decorator(func: _F) -> _F:
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
