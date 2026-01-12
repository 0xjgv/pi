"""Shared Rich console with custom theme for consistent CLI output."""

from rich.console import Console
from rich.theme import Theme

# Named styles for semantic consistency
custom_theme = Theme({
    "heading": "bold cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
    "muted": "dim",
    "path": "cyan",
})

# Singleton console instance
console = Console(theme=custom_theme)


def print_heading(text: str) -> None:
    """Print text with heading style."""
    console.print(text, style="heading")


def print_success(text: str) -> None:
    """Print text with success style."""
    console.print(f"[success]\u2713[/success] {text}")


def print_error(text: str) -> None:
    """Print text with error style."""
    console.print(f"[error]\u2717[/error] {text}")


def print_path(label: str, path: str) -> None:
    """Print labeled path with muted style."""
    console.print(f"[muted]{label}:[/muted] [path]{path}[/path]")
