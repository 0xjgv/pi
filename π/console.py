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
