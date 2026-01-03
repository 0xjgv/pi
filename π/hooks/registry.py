"""Language checker registry system."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LanguageChecker:
    """Metadata for a language checker.

    Attributes:
        func: Checker function (path, tool_name) -> exit_code
        scope: "file" for per-file checks, "project" for project-wide
        project_markers: Files that identify project root (for project scope)
    """

    func: Callable[[Path, str | None], int]
    scope: str  # "file" or "project"
    project_markers: list[str]


# Global registry of language checkers by file extension
_registry: dict[str, LanguageChecker] = {}


def language_checker(
    extensions: list[str],
    scope: str = "file",
    project_markers: list[str] | None = None,
) -> Callable:
    """Decorator to register functions as language checkers.

    Args:
        extensions: List of file extensions to handle (e.g., ['.py', '.pyx'])
        scope: "file" for per-file checks, "project" for project-wide checks
        project_markers: For project-scope, files that identify project root

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        checker = LanguageChecker(
            func=func,
            scope=scope,
            project_markers=project_markers or [],
        )
        for ext in extensions:
            _registry[ext.lower()] = checker
        return func

    return decorator


def get_checker(extension: str) -> LanguageChecker | None:
    """Get the checker for a file extension.

    Args:
        extension: File extension including dot (e.g., '.py')

    Returns:
        LanguageChecker if registered, None otherwise
    """
    return _registry.get(extension.lower())
