"""Tests for console module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rich.console import Console

from π.console import (
    console,
    custom_theme,
    print_error,
    print_heading,
    print_path,
    print_success,
)


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


class TestPrintHelpers:
    """Tests for print helper functions."""

    @patch("π.console.console")
    def test_print_heading(self, mock_console: MagicMock) -> None:
        """print_heading calls console.print with heading style."""
        print_heading("Test Heading")
        mock_console.print.assert_called_once_with("Test Heading", style="heading")

    @patch("π.console.console")
    def test_print_success_includes_checkmark(self, mock_console: MagicMock) -> None:
        """print_success includes checkmark character."""
        print_success("Operation succeeded")
        call_args = mock_console.print.call_args[0][0]
        assert "\u2713" in call_args  # Unicode checkmark
        assert "Operation succeeded" in call_args

    @patch("π.console.console")
    def test_print_error_includes_x_mark(self, mock_console: MagicMock) -> None:
        """print_error includes X mark character."""
        print_error("Operation failed")
        call_args = mock_console.print.call_args[0][0]
        assert "\u2717" in call_args  # Unicode X mark
        assert "Operation failed" in call_args

    @patch("π.console.console")
    def test_print_path_formats_label_and_path(self, mock_console: MagicMock) -> None:
        """print_path formats label and path with correct styles."""
        print_path("Output", "/path/to/file.txt")
        call_args = mock_console.print.call_args[0][0]
        assert "Output" in call_args
        assert "/path/to/file.txt" in call_args
        # Should use muted and path styles
        assert "[muted]" in call_args
        assert "[path]" in call_args
