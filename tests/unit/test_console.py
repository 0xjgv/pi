"""Tests for console module."""

from __future__ import annotations

from rich.console import Console

from π.console import console, custom_theme


class TestCustomTheme:
    """Tests for custom theme configuration."""

    def test_heading_style_exists(self) -> None:
        """Theme defines heading style."""
        assert "heading" in custom_theme.styles

    def test_success_style_exists(self) -> None:
        """Theme defines success style."""
        assert "success" in custom_theme.styles

    def test_warning_style_exists(self) -> None:
        """Theme defines warning style."""
        assert "warning" in custom_theme.styles

    def test_error_style_exists(self) -> None:
        """Theme defines error style."""
        assert "error" in custom_theme.styles

    def test_muted_style_exists(self) -> None:
        """Theme defines muted style."""
        assert "muted" in custom_theme.styles

    def test_path_style_exists(self) -> None:
        """Theme defines path style."""
        assert "path" in custom_theme.styles


class TestConsoleSingleton:
    """Tests for console singleton instance."""

    def test_console_is_console_instance(self) -> None:
        """console is a Rich Console instance."""
        assert isinstance(console, Console)

    def test_console_has_custom_theme(self) -> None:
        """console uses the custom theme."""
        # Verify custom styles are accessible by getting them from the console
        # The console.get_style method returns styles that are defined in the theme
        style = console.get_style("heading")
        assert style is not None
